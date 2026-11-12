"""Persist current state and its historical event in the same transaction."""
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .catalog import invalidate_catalog
from .models import Favorite, Movie, Rating, UserInteraction, Watched, Watchlist
from .recommendation import invalidate_index, invalidate_user


LIST_MODELS = {"favorites": Favorite, "watchlist": Watchlist, "watched": Watched}


def require_movie(db: Session, movie_id: int) -> Movie:
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return movie


def record(db: Session, user_id: int, movie_id: int, kind: str, value: float | None) -> None:
    db.add(UserInteraction(user_id=user_id, movie_id=movie_id, type=kind, value=value))


def refresh_rating_aggregate(db: Session, movie_id: int) -> None:
    movie = require_movie(db, movie_id)
    average, count = db.execute(select(func.avg(Rating.value), func.count(Rating.value)).where(Rating.movie_id == movie_id)).one()
    user_count = int(count or 0)
    total_count = movie.base_rating_count + user_count
    weighted_sum = movie.base_rating * movie.base_rating_count + 2 * float(average or 0) * user_count
    movie.avg_rating = weighted_sum / total_count if total_count else 0
    movie.rating_count = total_count


def set_rating(db: Session, user_id: int, movie_id: int, value: int) -> Rating:
    movie = require_movie(db, movie_id)
    rating = db.get(Rating, (user_id, movie_id))
    if rating is None:
        rating = Rating(user_id=user_id, movie_id=movie_id, value=value)
        db.add(rating)
    else:
        rating.value = value
    record(db, user_id, movie_id, "rating_set", value)
    db.flush()
    refresh_rating_aggregate(db, movie_id)
    db.commit()
    invalidate_index(db)
    invalidate_catalog(db)
    db.refresh(rating)
    return rating


def set_list_state(db: Session, user_id: int, movie_id: int, list_name: str, enabled: bool) -> bool:
    require_movie(db, movie_id)
    model = LIST_MODELS[list_name]
    existing = db.get(model, (user_id, movie_id))
    if enabled and existing is None:
        db.add(model(user_id=user_id, movie_id=movie_id))
    elif not enabled and existing is not None:
        db.delete(existing)
    else:
        return False
    record(db, user_id, movie_id, f"{list_name}_{'added' if enabled else 'removed'}", float(enabled))
    db.commit()
    invalidate_user(db, user_id)
    return True
