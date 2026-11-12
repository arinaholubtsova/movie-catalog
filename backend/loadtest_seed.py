"""Create an isolated 20k-movie, 20-user dataset for performance verification."""
import json
from pathlib import Path

from sqlalchemy import func, insert, select

from app.auth import hash_password, make_token
from app.database import SessionLocal
from app.models import Movie, Rating, User, Watched
from seed import seed


KEYWORDS = [
    "space, discovery, crew", "family, drama, friendship", "crime, detective, mystery",
    "action, hero, city", "music, ambition, stage", "history, war, courage",
    "comedy, travel, friendship", "thriller, suspense, code", "fantasy, magic, adventure",
    "science, future, technology",
]


def prepare(output: Path):
    seed()
    with SessionLocal() as db:
        count = db.scalar(select(func.count()).select_from(Movie)) or 0
        if count > 20_000:
            raise ValueError(f"Dataset has {count} movies; expected at most 20000")
        pending = []
        for index in range(count + 1, 20_001):
            pending.append({
                "title": f"Performance Film {index:05d}", "year": 1980 + index % 45,
                "overview": f"Performance dataset movie {index}",
                "keywords": KEYWORDS[index % len(KEYWORDS)],
                "avg_rating": 5.0 + (index % 25) / 5,
                "rating_count": 10 + index % 80,
                "external_id": f"perf-{index:05d}",
            })
            if len(pending) == 1000:
                db.execute(insert(Movie), pending)
                db.commit()
                pending.clear()
        if pending:
            db.execute(insert(Movie), pending)
            db.commit()
        password_hash = hash_password("performance-only-account")
        users = []
        for index in range(20):
            email = f"performance-{index:02d}@example.test"
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(email=email, password_hash=password_hash)
                db.add(user)
                db.flush()
            users.append(user)
            for movie_id in range(1 + index * 5, 6 + index * 5):
                if db.get(Rating, (user.id, movie_id)) is None:
                    db.add(Rating(user_id=user.id, movie_id=movie_id, value=5))
            if db.get(Watched, (user.id, 1 + index * 5)) is None:
                db.add(Watched(user_id=user.id, movie_id=1 + index * 5))
        db.commit()
        tokens = [make_token(user) for user in users]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(tokens), encoding="utf-8")
        final_count = db.scalar(select(func.count()).select_from(Movie))
        print(f"movies={final_count} users={len(users)} tokens_file={output}")


if __name__ == "__main__":
    prepare(Path(__file__).resolve().parents[1] / ".run" / "loadtest_tokens.json")
