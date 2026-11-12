import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.database import Base, get_db
from app.main import app
from app.models import Genre, Movie, User


@pytest.fixture
def context():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override
    with factory() as db:
        sci = Genre(name="Sci-Fi")
        drama = Genre(name="Drama")
        db.add_all([sci, drama])
        db.flush()
        db.add_all([
            Movie(title="Space One", year=2020, overview="Space journey", keywords="space", avg_rating=9.0, rating_count=20, genres=[sci]),
            Movie(title="Space Two", year=2021, keywords="space", avg_rating=8.0, rating_count=10, genres=[sci]),
            Movie(title="Drama One", year=2019, keywords="family", avg_rating=9.6, rating_count=30, genres=[drama]),
            Movie(title="Drama Two", year=2022, keywords="family", avg_rating=7.0, rating_count=5, genres=[drama]),
        ])
        db.add(User(email="admin@example.com", password_hash=hash_password("admin-password"), role="admin"))
        db.commit()
    with TestClient(app) as client:
        yield client, factory
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def user_headers(context):
    client, _ = context
    assert client.post("/auth/register", json={"email": "user@example.com", "password": "good-password"}).status_code == 201
    token = client.post("/auth/login", json={"email": "user@example.com", "password": "good-password"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(context):
    client, _ = context
    token = client.post("/auth/login", json={"email": "admin@example.com", "password": "admin-password"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
