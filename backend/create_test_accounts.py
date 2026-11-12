"""Create local demo accounts once and save their credentials outside Git."""
import secrets
from pathlib import Path

from sqlalchemy import select

from app.auth import hash_password
from app.database import SessionLocal
from app.models import User


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "TEST_ACCOUNTS.txt"
ACCOUNTS = (("admin.demo@example.com", "admin"), ("user.demo@example.com", "user"))


def main() -> None:
    with SessionLocal() as db:
        if OUTPUT.exists() or any(db.scalar(select(User.id).where(User.email == email)) for email, _ in ACCOUNTS):
            raise RuntimeError("Demo accounts or credential file already exist; passwords were not changed")
        credentials = [(email, role, secrets.token_urlsafe(18)) for email, role in ACCOUNTS]
        db.add_all(User(email=email, role=role, password_hash=hash_password(password)) for email, role, password in credentials)
        db.commit()
    lines = ["Тестові акаунти локального каталогу", "Адреса: http://localhost:5174", ""]
    for email, role, password in credentials:
        lines.extend((f"Роль: {role}", f"Email: {email}", f"Пароль: {password}", ""))
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print("Created:", ", ".join(f"{email} ({role})" for email, role, _ in credentials))


if __name__ == "__main__":
    main()
