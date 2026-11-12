from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import select

from app.auth import SECRET
from app.models import Favorite, Movie, Rating, Recommendation, User, UserInteraction, Watched, Watchlist


def test_catalog_search_filter_sort_pagination(context):
    client, _ = context
    result = client.get("/movies", params={"q": "space", "genre": "Sci-Fi", "min_rating": 8, "sort": "year", "year_from": 2020, "year_to": 2021}).json()
    assert result["total"] == 2
    assert result["items"][0]["title"] == "Space Two"
    assert result["page_size"] == 20
    assert client.get("/movies/1").json()["overview"] == "Space journey"
    assert client.get("/movies/999").status_code == 404


def test_search_boundaries_and_twenty_item_pages(context):
    client, factory = context
    assert client.get("/movies", params={"year": 2021, "min_rating": 8, "sort": "rating_desc"}).json()["items"][0]["title"] == "Space Two"
    assert client.get("/movies", params={"q": "journey"}).json()["total"] == 1
    assert client.get("/movies", params={"genre": "Action"}).json()["total"] == 0
    for params in ({"min_rating": 10.1}, {"genre": "Unknown"}, {"year_from": 2022, "year_to": 2020}):
        assert client.get("/movies", params=params).status_code == 422
    with factory() as db:
        db.add_all(Movie(title=f"Bulk {i:02}", year=2020) for i in range(21))
        db.commit()
    first = client.get("/movies", params={"q": "Bulk"}).json()
    second = client.get("/movies", params={"q": "Bulk", "page": 2}).json()
    assert first["total"] == 21 and len(first["items"]) == 20
    assert len(second["items"]) == 1 and first["page_size"] == second["page_size"] == 20


def test_cached_search_refreshes_after_rating_and_catalog_changes(context, user_headers, admin_headers):
    client, _ = context
    params = {"q": "Space", "min_rating": 8}
    assert client.get("/movies", params=params).json()["total"] == 2
    assert client.put("/me/ratings/1", headers=user_headers, json={"value": 1}).status_code == 200
    assert client.get("/movies", params=params).json()["total"] == 1
    new_movie = client.post("/admin/movies", headers=admin_headers, json={"title": "Space Three", "year": 2024}).json()
    assert client.get("/movies", params={"q": "Space"}).json()["total"] == 3
    assert client.delete(f"/admin/movies/{new_movie['id']}", headers=admin_headers).status_code == 204
    assert client.get("/movies", params={"q": "Space"}).json()["total"] == 2


def test_auth_registration_logout_and_authorization(context, user_headers):
    client, _ = context
    assert client.post("/auth/register", json={"email": "user@example.com", "password": "good-password"}).status_code == 409
    assert client.post("/auth/login", json={"email": "user@example.com", "password": "wrong-password"}).status_code == 401
    assert client.get("/me/recommendations").status_code == 401
    assert client.post("/admin/genres", headers=user_headers, json={"name": "Crime"}).status_code == 403
    assert client.post("/auth/logout", headers=user_headers).status_code == 204
    assert client.get("/auth/me", headers=user_headers).status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer broken"}).status_code == 401


def test_expired_token_is_rejected(context, user_headers):
    client, _ = context
    user_id = client.get("/auth/me", headers=user_headers).json()["id"]
    expired = jwt.encode({"sub": str(user_id), "jti": "expired-test", "role": "user", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)}, SECRET, algorithm="HS256")
    assert client.get("/me/recommendations", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_rating_log_persistence_and_update(context, user_headers):
    client, factory = context
    assert client.put("/me/ratings/1", headers=user_headers, json={"value": 0}).status_code == 422
    assert client.put("/me/ratings/1", headers=user_headers, json={"value": 5}).status_code == 200
    assert client.put("/me/ratings/1", headers=user_headers, json={"value": 4}).status_code == 200
    assert client.get("/movies/1").json()["avg_rating"] == 8
    with factory() as db:
        assert len(list(db.scalars(select(Rating)))) == 1
        assert db.scalar(select(Rating)).value == 4
        events = list(db.scalars(select(UserInteraction).order_by(UserInteraction.id)))
        assert [event.value for event in events] == [5, 4]
        assert all(event.timestamp is not None and event.user_id and event.movie_id for event in events)


def test_catalog_base_rating_is_preserved_when_users_rate(context, user_headers):
    client, factory = context
    with factory() as db:
        movie = Movie(title="Baseline Film", year=2024, base_rating=8.0, base_rating_count=100, avg_rating=8.0, rating_count=100)
        db.add(movie)
        db.commit()
        movie_id = movie.id
    assert client.put(f"/me/ratings/{movie_id}", headers=user_headers, json={"value": 5}).status_code == 200
    detail = client.get(f"/movies/{movie_id}").json()
    assert detail["rating_count"] == 101
    assert detail["avg_rating"] == (8.0 * 100 + 10.0) / 101


def test_lists_history_and_watched_exclusion(context, user_headers):
    client, factory = context
    for name in ("favorites", "watchlist", "watched"):
        assert client.put(f"/me/{name}/1", headers=user_headers).status_code == 200
        assert client.put(f"/me/{name}/1", headers=user_headers).json()["changed"] is False
        assert len(client.get(f"/me/{name}", headers=user_headers).json()) == 1
    history = client.get("/me/history", headers=user_headers).json()
    assert len(history) == 3
    assert history[0]["movie"]["title"] == "Space One"
    assert history[0]["movie_id"] == history[0]["movie"]["id"]
    ids = [row["movie"]["id"] for row in client.get("/me/recommendations", headers=user_headers).json()]
    assert 1 not in ids
    assert client.delete("/me/favorites/1", headers=user_headers).json()["changed"] is True
    with factory() as db:
        assert db.scalar(select(Favorite)) is None
        assert len(list(db.scalars(select(UserInteraction)))) == 4


def test_account_email_password_and_personal_data_deletion(context, user_headers):
    client, factory = context
    assert client.put("/me/email", json={"email": "new@example.com"}).status_code == 401
    assert client.put("/me/email", headers=user_headers, json={"email": "admin@example.com"}).status_code == 409
    assert client.put("/me/email", headers=user_headers, json={"email": "NEW@EXAMPLE.COM"}).json()["email"] == "new@example.com"
    assert client.put("/me/password", headers=user_headers, json={"current_password": "wrong", "new_password": "new-password"}).status_code == 403
    assert client.put("/me/password", headers=user_headers, json={"current_password": "good-password", "new_password": "new-password"}).status_code == 204
    assert client.post("/auth/login", json={"email": "new@example.com", "password": "good-password"}).status_code == 401
    assert client.post("/auth/login", json={"email": "new@example.com", "password": "new-password"}).status_code == 200
    assert client.put("/me/ratings/1", headers=user_headers, json={"value": 5}).status_code == 200
    for name in ("favorites", "watchlist", "watched"):
        assert client.put(f"/me/{name}/1", headers=user_headers).status_code == 200
    assert client.post("/auth/register", json={"email": "other@example.com", "password": "other-password"}).status_code == 201
    other_token = client.post("/auth/login", json={"email": "other@example.com", "password": "other-password"}).json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}
    assert client.put("/me/ratings/1", headers=other_headers, json={"value": 3}).status_code == 200
    with factory() as db:
        user = db.scalar(select(User).where(User.email == "new@example.com"))
        db.add(Recommendation(user_id=user.id, movie_id=2, score=.5, reason="test"))
        db.commit()
        user_id = user.id
    assert client.request("DELETE", "/me/account", headers=user_headers, json={"password": "wrong", "confirmation": "DELETE"}).status_code == 403
    assert client.request("DELETE", "/me/account", headers=user_headers, json={"password": "new-password", "confirmation": "NO"}).status_code == 403
    assert client.request("DELETE", "/me/account", headers=user_headers, json={"password": "new-password", "confirmation": "DELETE"}).status_code == 204
    assert client.get("/auth/me", headers=user_headers).status_code == 401
    assert client.get("/movies/1").json()["avg_rating"] == 6
    assert client.get("/auth/me", headers=other_headers).status_code == 200
    with factory() as db:
        assert db.get(User, user_id) is None
        for model in (Rating, Favorite, Watchlist, Watched, UserInteraction, Recommendation):
            assert db.scalar(select(model).where(model.user_id == user_id)) is None
        assert db.scalar(select(Rating).where(Rating.movie_id == 1)).value == 3


def test_recommendation_adapts_and_explains(context, user_headers):
    client, _ = context
    cold = client.get("/me/recommendations?k=2", headers=user_headers).json()
    assert len(cold) == 2 and all(row["reason"] for row in cold)
    client.put("/me/ratings/1", headers=user_headers, json={"value": 5})
    client.put("/me/watched/1", headers=user_headers)
    first = client.get("/me/recommendations?k=4", headers=user_headers).json()
    assert first[0]["movie"]["id"] == 2
    client.put("/me/ratings/3", headers=user_headers, json={"value": 5})
    second = client.get("/me/recommendations?k=4", headers=user_headers).json()
    before = {row["movie"]["id"]: row["score"] for row in first}
    after = {row["movie"]["id"]: row["score"] for row in second}
    assert after[4] > before[4]
    assert all(0 <= row["score"] <= 1 and row["reason"] for row in second)
    assert [row["score"] for row in second] == sorted([row["score"] for row in second], reverse=True)
    assert len(client.get("/me/recommendations?k=50", headers=user_headers).json()) == 3
    assert client.get("/movies/1/similar?k=1").json()[0]["movie"]["id"] == 2


def test_cached_recommendations_refresh_after_list_change(context, user_headers):
    client, _ = context
    cold = client.get("/me/recommendations?k=3", headers=user_headers).json()
    assert all(row["reason"] == "Популярний фільм для початку" for row in cold)
    assert client.put("/me/watchlist/1", headers=user_headers).status_code == 200
    personalized = client.get("/me/recommendations?k=3", headers=user_headers).json()
    assert any(row["reason"].startswith("Спільні ознаки:") for row in personalized)
    assert client.delete("/me/watchlist/1", headers=user_headers).status_code == 200
    reset = client.get("/me/recommendations?k=3", headers=user_headers).json()
    assert all(row["reason"] == "Популярний фільм для початку" for row in reset)


def test_admin_crud_and_sync_config(context, admin_headers):
    client, _ = context
    genre = client.post("/admin/genres", headers=admin_headers, json={"name": "Comedy"}).json()
    movie = client.post("/admin/movies", headers=admin_headers, json={"title": "New Film", "year": 2024, "genre_ids": [genre["id"]], "actors": ["Actor One"], "directors": ["Director One"]}).json()
    assert movie["genres"] == ["Comedy"]
    assert client.patch(f"/admin/movies/{movie['id']}", headers=admin_headers, json={"title": "Edited Film"}).json()["title"] == "Edited Film"
    assert client.delete(f"/admin/genres/{genre['id']}", headers=admin_headers).status_code == 409
    assert client.delete(f"/admin/movies/{movie['id']}", headers=admin_headers).status_code == 204
    assert client.delete(f"/admin/genres/{genre['id']}", headers=admin_headers).status_code == 204
    assert client.post("/admin/sync", headers=admin_headers).status_code == 503


def test_posters_and_personal_movie_state(context, user_headers, admin_headers):
    client, _ = context
    created = client.post("/admin/movies", headers=admin_headers, json={"title": "Poster Film", "year": 2024, "poster_url": "/posters/demo-orbit.svg"})
    assert created.status_code == 201
    movie_id = created.json()["id"]
    assert client.get(f"/movies/{movie_id}").json()["poster_url"] == "/posters/demo-orbit.svg"
    assert client.get("/movies", params={"q": "Poster Film"}).json()["items"][0]["poster_url"] == "/posters/demo-orbit.svg"
    assert client.patch(f"/admin/movies/{movie_id}", headers=admin_headers, json={"poster_url": "http://example.test/poster.jpg"}).status_code == 422
    assert client.patch(f"/admin/movies/{movie_id}", headers=admin_headers, json={"poster_url": "https://example.test/poster.jpg"}).json()["poster_url"] == "https://example.test/poster.jpg"
    assert client.get(f"/me/movie-state/{movie_id}").status_code == 401
    assert client.get(f"/me/movie-state/{movie_id}", headers=user_headers).json() == {"rating": None, "lists": {"favorites": False, "watchlist": False, "watched": False}}
    assert client.put(f"/me/ratings/{movie_id}", headers=user_headers, json={"value": 4}).status_code == 200
    assert client.put(f"/me/favorites/{movie_id}", headers=user_headers).status_code == 200
    assert client.get(f"/me/movie-state/{movie_id}", headers=user_headers).json() == {"rating": 4, "lists": {"favorites": True, "watchlist": False, "watched": False}}


def test_metadata_sync_counts_and_isolates_bad_records(context, admin_headers, monkeypatch):
    client, _ = context
    from app import main

    class Feed:
        def raise_for_status(self):
            pass

        def json(self):
            return [
                {"title": "Imported", "year": 2024, "external_id": "ext-1", "genre_ids": [1]},
                {"title": "Bad", "year": 2024, "external_id": "ext-2", "genre_ids": [999]},
                {"title": "No ID", "year": 2024},
            ]

    monkeypatch.setenv("METADATA_URL", "https://example.test/feed")
    monkeypatch.setattr(main.httpx, "get", lambda *_args, **_kwargs: Feed())
    assert client.post("/admin/sync", headers=admin_headers).json() == {"created": 1, "updated": 0, "skipped": 2}
    assert client.get("/movies", params={"q": "Bad"}).json()["total"] == 0
    assert client.post("/admin/sync", headers=admin_headers).json() == {"created": 0, "updated": 1, "skipped": 2}


def test_recommendation_index_refreshes_after_catalog_change(context, user_headers, admin_headers):
    client, _ = context
    client.put("/me/ratings/1", headers=user_headers, json={"value": 5})
    before = client.get("/me/recommendations?k=10", headers=user_headers).json()
    movie = client.post("/admin/movies", headers=admin_headers, json={
        "title": "New Space Film", "year": 2024, "keywords": "space", "genre_ids": [1]
    }).json()
    after_create = client.get("/me/recommendations?k=10", headers=user_headers).json()
    assert len(after_create) == len(before) + 1
    assert movie["id"] in [row["movie"]["id"] for row in after_create]
    client.delete(f"/admin/movies/{movie['id']}", headers=admin_headers)
    after_delete = client.get("/me/recommendations?k=10", headers=user_headers).json()
    assert movie["id"] not in [row["movie"]["id"] for row in after_delete]
