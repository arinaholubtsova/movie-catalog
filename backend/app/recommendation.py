"""Content-based baseline from sections 1.6 and 2.1 of the project design."""
from collections import defaultdict
from dataclasses import dataclass
from heapq import nlargest
from math import sqrt
from threading import Lock

from sqlalchemy import select
from sqlalchemy.orm import Session

from .catalog import movie_json
from .models import Favorite, Movie, Rating, Watched, Watchlist


@dataclass(frozen=True)
class FeatureEntry:
    movie_id: int
    features: dict[str, float]
    avg_rating: float
    rating_count: int


_index_lock = Lock()
_index_cache: dict[object, list[FeatureEntry]] = {}
_recommendation_lock = Lock()
_recommendation_cache: dict[tuple[object, int, int], tuple[dict, ...]] = {}
_cache_generation: dict[object, int] = {}


def feature_index(db: Session) -> list[FeatureEntry]:
    engine = db.get_bind()
    with _index_lock:
        if engine not in _index_cache:
            movies = db.scalars(select(Movie).order_by(Movie.id))
            _index_cache[engine] = [FeatureEntry(movie.id, movie_features(movie), movie.avg_rating, movie.rating_count) for movie in movies]
        return _index_cache[engine]


def invalidate_index(db: Session) -> None:
    with _index_lock:
        _index_cache.pop(db.get_bind(), None)
    with _recommendation_lock:
        engine = db.get_bind()
        _cache_generation[engine] = _cache_generation.get(engine, 0) + 1
        for key in [key for key in _recommendation_cache if key[0] is engine]:
            del _recommendation_cache[key]


def invalidate_user(db: Session, user_id: int) -> None:
    with _recommendation_lock:
        engine = db.get_bind()
        _cache_generation[engine] = _cache_generation.get(engine, 0) + 1
        for key in [key for key in _recommendation_cache if key[0] is engine and key[1] == user_id]:
            del _recommendation_cache[key]


def movie_features(movie: Movie) -> dict[str, float]:
    features: dict[str, float] = {}
    for genre in movie.genres:
        features[f"genre:{genre.name.casefold()}"] = 1.0
    for actor in movie.actors[:5]:
        features[f"actor:{actor.name.casefold()}"] = 1.0
    for director in movie.directors:
        features[f"director:{director.name.casefold()}"] = 1.0
    for word in (movie.keywords or "").split(","):
        word = word.strip().casefold()
        if word:
            features[f"keyword:{word}"] = 1.0
    return features


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(value * right.get(key, 0.0) for key, value in left.items())
    left_norm = sqrt(sum(value * value for value in left.values()))
    right_norm = sqrt(sum(value * value for value in right.values()))
    return min(1.0, max(0.0, dot / (left_norm * right_norm))) if left_norm and right_norm else 0.0


def interaction_weights(db: Session, user_id: int) -> dict[int, float]:
    ratings = {r.movie_id: max((r.value - 3) / 2, 0) for r in db.scalars(select(Rating).where(Rating.user_id == user_id))}
    favorites = set(db.scalars(select(Favorite.movie_id).where(Favorite.user_id == user_id)))
    watched = set(db.scalars(select(Watched.movie_id).where(Watched.user_id == user_id)))
    watchlist = set(db.scalars(select(Watchlist.movie_id).where(Watchlist.user_id == user_id)))
    return {movie_id: weight for movie_id in ratings.keys() | favorites | watched | watchlist
            if (weight := .60 * ratings.get(movie_id, 0) + .25 * (movie_id in favorites) + .10 * (movie_id in watched) + .05 * (movie_id in watchlist)) > 0}


def build_profile(movies: list[Movie], weights: dict[int, float]) -> dict[str, float]:
    total = 0.0
    weighted: dict[str, float] = defaultdict(float)
    for movie in movies:
        weight = weights.get(movie.id, 0)
        if weight <= 0:
            continue
        features = movie_features(movie)
        if not features:
            continue
        total += weight
        for key, value in features.items():
            weighted[key] += weight * value
    return {key: value / total for key, value in weighted.items()} if total else {}


def profile_from_index(index: list[FeatureEntry], weights: dict[int, float]) -> dict[str, float]:
    weighted: dict[str, float] = defaultdict(float)
    total = 0.0
    for entry in index:
        weight = weights.get(entry.movie_id, 0)
        if weight <= 0 or not entry.features:
            continue
        total += weight
        for key, value in entry.features.items():
            weighted[key] += weight * value
    return {key: value / total for key, value in weighted.items()} if total else {}


def reason(profile: dict[str, float], features: dict[str, float]) -> str:
    matches = nlargest(2, ((key, value * features.get(key, 0)) for key, value in profile.items()), key=lambda item: item[1])
    labels = [key.split(":", 1)[1] for key, score in matches if score > 0]
    return "Спільні ознаки: " + ", ".join(labels) if labels else "Доступний фільм із каталогу"


def recommend(db: Session, user_id: int, k: int) -> list[dict]:
    engine = db.get_bind()
    cache_key = (engine, user_id, k)
    with _recommendation_lock:
        cached = _recommendation_cache.get(cache_key)
        generation = _cache_generation.get(engine, 0)
    if cached is not None:
        return list(cached)
    index = feature_index(db)
    watched_ids = set(db.scalars(select(Watched.movie_id).where(Watched.user_id == user_id)))
    profile = profile_from_index(index, interaction_weights(db, user_id))
    candidates = [entry for entry in index if entry.movie_id not in watched_ids]
    if not profile:
        ranked = nlargest(k, candidates, key=lambda entry: (entry.avg_rating, entry.rating_count, -entry.movie_id))
        result = tuple((entry.movie_id, 0.0, "Популярний фільм для початку") for entry in ranked)
    else:
        scored = ((cosine(profile, entry.features), entry) for entry in candidates)
        ranked = nlargest(k, scored, key=lambda item: (item[0], -item[1].movie_id))
        result = tuple((entry.movie_id, score, reason(profile, entry.features)) for score, entry in ranked)
    response = resolve_recommendations(db, result)
    with _recommendation_lock:
        if _cache_generation.get(engine, 0) == generation:
            _recommendation_cache[cache_key] = tuple(response)
    return response


def resolve_recommendations(db: Session, entries: tuple[tuple[int, float, str], ...]) -> list[dict]:
    movies = {movie.id: movie for movie in db.scalars(select(Movie).where(Movie.id.in_([movie_id for movie_id, _, _ in entries])))}
    return [{"movie": movie_json(movies[movie_id]), "score": score, "reason": explanation} for movie_id, score, explanation in entries if movie_id in movies]


def similar(db: Session, movie_id: int, k: int) -> list[dict]:
    index = feature_index(db)
    source = next((entry for entry in index if entry.movie_id == movie_id), None)
    if source is None:
        return []
    ranked = nlargest(k, ((cosine(source.features, entry.features), entry) for entry in index if entry.movie_id != movie_id), key=lambda item: (item[0], -item[1].movie_id))
    movies = {movie.id: movie for movie in db.scalars(select(Movie).where(Movie.id.in_([entry.movie_id for _, entry in ranked])))}
    return [{"movie": movies[entry.movie_id], "score": score} for score, entry in ranked]
