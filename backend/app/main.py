import os
from datetime import datetime, timezone

import httpx
import jwt
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import SECRET, admin_user, bearer, current_user, hash_password, make_token, verify_password
from .catalog import invalidate_catalog, movie_json, search_movies
from .database import get_db
from .interactions import LIST_MODELS, refresh_rating_aggregate, require_movie, set_list_state, set_rating
from .models import Actor, Director, Favorite, Genre, Movie, Rating, Recommendation, RevokedToken, User, UserInteraction, Watched, Watchlist
from .recommendation import invalidate_index, recommend, similar
from .schemas import AccountDeleteIn, EmailChangeIn, GENRE_NAMES, GenreIn, LoginIn, MovieIn, MoviePatch, PasswordChangeIn, RatingIn, RegisterIn

app = FastAPI(title="Movie Catalog API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","), allow_methods=["*"], allow_headers=["*"])


def names(db: Session, model, values: list[str]):
    result = []
    for raw in values:
        name = raw.strip()
        if not name:
            continue
        item = db.scalar(select(model).where(model.name == name))
        if item is None:
            item = model(name=name)
            db.add(item)
        result.append(item)
    return result


def apply_movie(db: Session, movie: Movie, data: dict):
    for key in ("title", "year", "overview", "keywords", "poster_url", "external_id"):
        if key in data:
            setattr(movie, key, data[key])
    if "genre_ids" in data:
        genres = list(db.scalars(select(Genre).where(Genre.id.in_(data["genre_ids"])))) if data["genre_ids"] else []
        if len(genres) != len(set(data["genre_ids"])):
            raise HTTPException(status_code=422, detail="Unknown genre id")
        movie.genres = genres
    for key, model in (("actors", Actor), ("directors", Director)):
        if key in data:
            setattr(movie, key, names(db, model, data[key]))


def commit(db: Session):
    try:
        db.commit()
        invalidate_index(db)
        invalidate_catalog(db)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conflicting or referenced record") from None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/register", status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=email, password_hash=hash_password(data.password))
    db.add(user)
    commit(db)
    return {"id": user.id, "email": user.email}


@app.post("/auth/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": make_token(user), "token_type": "bearer", "role": user.role}


@app.post("/auth/logout", status_code=204)
def logout(credentials: HTTPAuthorizationCredentials = Depends(bearer), user: User = Depends(current_user), db: Session = Depends(get_db)):
    payload = jwt.decode(credentials.credentials, SECRET, algorithms=["HS256"])
    db.add(RevokedToken(jti=payload["jti"], expires_at=datetime.fromtimestamp(payload["exp"], timezone.utc)))
    db.commit()


@app.get("/auth/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "role": user.role}


@app.put("/me/email")
def change_email(data: EmailChangeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    owner = db.scalar(select(User).where(User.email == email))
    if owner is not None and owner.id != user.id:
        raise HTTPException(status_code=409, detail="Email already registered")
    user.email = email
    commit(db)
    return {"id": user.id, "email": user.email}


@app.put("/me/password", status_code=204)
def change_password(data: PasswordChangeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=403, detail="Current password is incorrect")
    user.password_hash = hash_password(data.new_password)
    commit(db)


@app.delete("/me/account", status_code=204)
def delete_account(data: AccountDeleteIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if data.confirmation != "DELETE" or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=403, detail="Account deletion confirmation failed")
    rated_ids = list(db.scalars(select(Rating.movie_id).where(Rating.user_id == user.id)))
    for model in (Recommendation, UserInteraction, Rating, Favorite, Watchlist, Watched):
        db.execute(delete(model).where(model.user_id == user.id))
    for movie_id in rated_ids:
        refresh_rating_aggregate(db, movie_id)
    db.delete(user)
    commit(db)


@app.get("/genres")
def genres(db: Session = Depends(get_db)):
    return [{"id": item.id, "name": item.name} for item in db.scalars(select(Genre).order_by(Genre.name))]


@app.get("/movies")
def movies(q: str | None = None, genre: str | None = None,
           year: int | None = Query(default=None, ge=1888, le=2200),
           year_from: int | None = Query(default=None, ge=1888, le=2200),
           year_to: int | None = Query(default=None, ge=1888, le=2200),
           min_rating: float | None = Query(default=None, ge=0, le=10),
           sort: str = Query(default="title", pattern="^(title|year|rating|title_asc|year_desc|rating_desc)$"),
           page: int = Query(default=1, ge=1), db: Session = Depends(get_db)):
    if year_from is not None and year_to is not None and year_from > year_to:
        raise HTTPException(status_code=422, detail="year_from must not exceed year_to")
    if genre:
        if genre.casefold() not in {name.casefold() for name in GENRE_NAMES}:
            raise HTTPException(status_code=422, detail="Unsupported genre")
    return search_movies(db, q, genre, year, year_from, year_to, min_rating, sort, page)


@app.get("/movies/{movie_id}")
def movie_detail(movie_id: int, db: Session = Depends(get_db)):
    return movie_json(require_movie(db, movie_id), detail=True)


@app.get("/movies/{movie_id}/similar")
def similar_movies(movie_id: int, k: int = Query(default=5, ge=1, le=50), db: Session = Depends(get_db)):
    require_movie(db, movie_id)
    return [{"movie": movie_json(item["movie"]), "score": item["score"]} for item in similar(db, movie_id, k)]


@app.put("/me/ratings/{movie_id}")
def rating(movie_id: int, data: RatingIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    result = set_rating(db, user.id, movie_id, data.value)
    return {"movie_id": result.movie_id, "value": result.value}


@app.get("/me/movie-state/{movie_id}")
def movie_state(movie_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_movie(db, movie_id)
    current_rating = db.scalar(select(Rating.value).where(Rating.user_id == user.id, Rating.movie_id == movie_id))
    lists = {name: db.scalar(select(model.movie_id).where(model.user_id == user.id, model.movie_id == movie_id)) is not None
             for name, model in LIST_MODELS.items()}
    return {"rating": current_rating, "lists": lists}


@app.put("/me/{list_name}/{movie_id}")
def add_to_list(list_name: str, movie_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if list_name not in LIST_MODELS:
        raise HTTPException(status_code=404, detail="Unknown list")
    changed = set_list_state(db, user.id, movie_id, list_name, True)
    return {"movie_id": movie_id, "active": True, "changed": changed}


@app.delete("/me/{list_name}/{movie_id}")
def remove_from_list(list_name: str, movie_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if list_name not in LIST_MODELS:
        raise HTTPException(status_code=404, detail="Unknown list")
    changed = set_list_state(db, user.id, movie_id, list_name, False)
    return {"movie_id": movie_id, "active": False, "changed": changed}


@app.get("/me/history")
def history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    events = list(db.scalars(select(UserInteraction).where(UserInteraction.user_id == user.id).order_by(UserInteraction.id.desc())))
    movie_ids = {event.movie_id for event in events}
    movies = {movie.id: movie for movie in db.scalars(select(Movie).where(Movie.id.in_(movie_ids)))} if movie_ids else {}
    return [{
        "id": event.id,
        "movie_id": event.movie_id,
        "movie": movie_json(movies[event.movie_id]) if event.movie_id in movies else None,
        "type": event.type,
        "value": event.value,
        "timestamp": event.timestamp,
    } for event in events]


@app.get("/me/recommendations")
def recommendations(k: int = Query(default=10, ge=1, le=50), user: User = Depends(current_user), db: Session = Depends(get_db)):
    return recommend(db, user.id, k)


@app.get("/me/{list_name}")
def list_movies(list_name: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if list_name not in LIST_MODELS:
        raise HTTPException(status_code=404, detail="Unknown list")
    model = LIST_MODELS[list_name]
    ids = list(db.scalars(select(model.movie_id).where(model.user_id == user.id)))
    return [movie_json(movie) for movie in db.scalars(select(Movie).where(Movie.id.in_(ids)).order_by(Movie.title))]


@app.post("/admin/genres", status_code=201)
def create_genre(data: GenreIn, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    genre = Genre(name=data.name.strip())
    db.add(genre)
    commit(db)
    return {"id": genre.id, "name": genre.name}


@app.put("/admin/genres/{genre_id}")
def update_genre(genre_id: int, data: GenreIn, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    genre = db.get(Genre, genre_id)
    if genre is None:
        raise HTTPException(status_code=404, detail="Genre not found")
    genre.name = data.name.strip()
    commit(db)
    return {"id": genre.id, "name": genre.name}


@app.delete("/admin/genres/{genre_id}", status_code=204)
def delete_genre(genre_id: int, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    genre = db.get(Genre, genre_id)
    if genre is None:
        raise HTTPException(status_code=404, detail="Genre not found")
    if db.scalar(select(Movie.id).where(Movie.genres.any(Genre.id == genre_id)).limit(1)) is not None:
        raise HTTPException(status_code=409, detail="Genre is used by a movie")
    db.delete(genre)
    commit(db)


@app.post("/admin/movies", status_code=201)
def create_movie(data: MovieIn, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    movie = Movie(title=data.title, year=data.year)
    db.add(movie)
    apply_movie(db, movie, data.model_dump())
    commit(db)
    return movie_json(movie, detail=True)


@app.patch("/admin/movies/{movie_id}")
def update_movie(movie_id: int, data: MoviePatch, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    movie = require_movie(db, movie_id)
    apply_movie(db, movie, data.model_dump(exclude_unset=True))
    commit(db)
    return movie_json(movie, detail=True)


@app.delete("/admin/movies/{movie_id}", status_code=204)
def delete_movie(movie_id: int, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    db.delete(require_movie(db, movie_id))
    commit(db)


@app.post("/admin/sync")
def sync_metadata(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    url = os.getenv("METADATA_URL")
    if not url:
        raise HTTPException(status_code=503, detail="METADATA_URL is not configured")
    try:
        response = httpx.get(url, timeout=10)
        response.raise_for_status()
        records = response.json()
        if not isinstance(records, list):
            raise ValueError("Metadata feed must be a JSON list")
    except (httpx.HTTPError, ValueError) as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    counts = {"created": 0, "updated": 0, "skipped": 0}
    for raw in records:
        try:
            data = MovieIn.model_validate(raw)
            if not data.external_id:
                counts["skipped"] += 1
                continue
            with db.begin_nested():
                movie = db.scalar(select(Movie).where(Movie.external_id == data.external_id))
                created = movie is None
                if created:
                    movie = Movie(title=data.title, year=data.year)
                    db.add(movie)
                apply_movie(db, movie, data.model_dump())
                db.flush()
            counts["created" if created else "updated"] += 1
        except (ValueError, HTTPException, TypeError):
            counts["skipped"] += 1
    commit(db)
    return counts
