import pytest

from app.recommendation import build_profile, cosine, movie_features
from app.models import Genre, Movie


def test_weighted_profile_matches_design_formula():
    drama = Genre(name="Drama")
    sci = Genre(name="Sci-Fi")
    a = Movie(id=1, title="A", year=2020, genres=[drama, sci])
    b = Movie(id=2, title="B", year=2021, genres=[sci])
    profile = build_profile([a, b], {1: 1.0, 2: .8})
    assert profile["genre:drama"] == pytest.approx(1 / 1.8, abs=1e-6)
    assert profile["genre:sci-fi"] == pytest.approx(1.0, abs=1e-6)
    assert cosine(profile, movie_features(a)) == pytest.approx(.961524, abs=1e-6)


def test_empty_and_zero_vectors():
    assert build_profile([], {}) == {}
    assert cosine({}, {"genre:drama": 1}) == 0
    assert cosine({"genre:drama": 1}, {"genre:sci-fi": 1}) == 0
