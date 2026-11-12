"""Exercise all personal writes while the isolated load-test server is busy."""
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Favorite, Rating, User, UserInteraction, Watched, Watchlist


ROOT = Path(__file__).resolve().parents[1]
tokens = json.loads((ROOT / ".run/loadtest_tokens.json").read_text(encoding="utf-8"))
accepted = []
failures = []

with httpx.Client(base_url="http://127.0.0.1:8001", timeout=40) as client:
    for index, token in enumerate(tokens):
        movie_id = 19_941 + index
        headers = {"Authorization": f"Bearer {token}"}
        for name, body in (("ratings", {"value": 4}), ("favorites", None), ("watchlist", None), ("watched", None)):
            try:
                response = client.put(f"/me/{name}/{movie_id}", json=body, headers=headers)
                if response.status_code == 200:
                    accepted.append((index, name, movie_id))
                else:
                    failures.append({"user": index, "operation": name, "status": response.status_code})
            except httpx.HTTPError as error:
                failures.append({"user": index, "operation": name, "error": type(error).__name__})

mismatches = []
with SessionLocal() as db:
    for index, name, movie_id in accepted:
        user_id = db.scalar(select(User.id).where(User.email == f"performance-{index:02d}@example.test"))
        model = {"ratings": Rating, "favorites": Favorite, "watchlist": Watchlist, "watched": Watched}[name]
        row = db.get(model, (user_id, movie_id))
        if row is None or (name == "ratings" and row.value != 4):
            mismatches.append({"user": index, "operation": name, "movie_id": movie_id, "reason": "current state missing"})
        event_type = "rating_set" if name == "ratings" else f"{name}_added"
        event = db.scalar(select(UserInteraction).where(UserInteraction.user_id == user_id, UserInteraction.movie_id == movie_id, UserInteraction.type == event_type))
        if event is None or event.timestamp is None:
            mismatches.append({"user": index, "operation": name, "movie_id": movie_id, "reason": "history event missing"})

report = {
    "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    "accepted_writes": len(accepted),
    "failed_writes": len(failures),
    "failures": failures,
    "persistence_mismatches": len(mismatches),
    "mismatches": mismatches,
}
output = ROOT / "reports/persistence-2026-11-04-final.json"
output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
