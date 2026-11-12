"""Check that every seeded movie has complete detail data."""
import sys
from pathlib import Path

from sqlalchemy import select


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.database import SessionLocal  # noqa: E402
from app.models import Movie  # noqa: E402


def main() -> None:
    with SessionLocal() as db:
        movies = list(db.scalars(select(Movie).order_by(Movie.title)))
        incomplete = [
            movie.title
            for movie in movies
            if not movie.overview.strip()
            or not movie.actors
            or not movie.directors
            or movie.avg_rating <= 0
            or movie.rating_count <= 0
        ]
    if incomplete:
        raise SystemExit(f"Incomplete movies: {', '.join(incomplete)}")
    print(f"Complete catalog records: {len(movies)}/{len(movies)}")


if __name__ == "__main__":
    main()
