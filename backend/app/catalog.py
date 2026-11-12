"""Catalog queries and a bounded cache of serialized search pages."""
from collections import OrderedDict
from threading import Lock

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Genre, Movie
from .schemas import GENRE_NAMES


_lock = Lock()
_pages: OrderedDict[tuple, dict] = OrderedDict()
_generation: dict[object, int] = {}
_MAX_PAGES = 256


def movie_json(movie: Movie, detail: bool = False) -> dict:
    data = {"id": movie.id, "title": movie.title, "year": movie.year, "genres": [genre.name for genre in movie.genres], "poster_url": movie.poster_url, "avg_rating": movie.avg_rating, "rating_count": movie.rating_count}
    if detail:
        data.update(overview=movie.overview, keywords=movie.keywords, directors=[person.name for person in movie.directors], actors=[person.name for person in movie.actors], external_id=movie.external_id)
    return data


def invalidate_catalog(db: Session) -> None:
    engine = db.get_bind()
    with _lock:
        _generation[engine] = _generation.get(engine, 0) + 1
        for key in [key for key in _pages if key[0] is engine]:
            del _pages[key]


def search_movies(db: Session, q: str | None, genre: str | None, year: int | None,
                  year_from: int | None, year_to: int | None, min_rating: float | None,
                  sort: str, page: int) -> dict:
    engine = db.get_bind()
    key = (engine, q, genre, year, year_from, year_to, min_rating, sort, page)
    with _lock:
        cached = _pages.get(key)
        generation = _generation.get(engine, 0)
        if cached is not None:
            _pages.move_to_end(key)
            return cached
    query = select(Movie)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(Movie.title.ilike(pattern) | Movie.overview.ilike(pattern) | Movie.keywords.ilike(pattern))
    if genre:
        query = query.where(Movie.genres.any(func.lower(Genre.name) == genre.casefold()))
    if year is not None:
        query = query.where(Movie.year == year)
    if year_from is not None:
        query = query.where(Movie.year >= year_from)
    if year_to is not None:
        query = query.where(Movie.year <= year_to)
    if min_rating is not None:
        query = query.where(Movie.avg_rating >= min_rating)
    order = {"title": Movie.title.asc(), "title_asc": Movie.title.asc(), "year": Movie.year.desc(), "year_desc": Movie.year.desc(), "rating": Movie.avg_rating.desc(), "rating_desc": Movie.avg_rating.desc()}[sort]
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    page_items = db.scalars(query.order_by(order, Movie.id).offset((page - 1) * 20).limit(20))
    result = {"items": [movie_json(movie) for movie in page_items], "total": total, "page": page, "page_size": 20}
    with _lock:
        if _generation.get(engine, 0) == generation:
            _pages[key] = result
            _pages.move_to_end(key)
            if len(_pages) > _MAX_PAGES:
                _pages.popitem(last=False)
    return result
