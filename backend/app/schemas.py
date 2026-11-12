from pydantic import BaseModel, EmailStr, Field, field_validator


GENRE_NAMES = (
    "Action", "Adventure", "Animation", "Comedy", "Crime", "Documentary",
    "Drama", "Fantasy", "Horror", "Mystery", "Romance", "Sci-Fi", "Thriller",
)


def validate_poster_url(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    value = value.strip()
    if value.startswith("https://") or value.startswith("/posters/"):
        return value
    raise ValueError("Poster URL must use HTTPS or start with /posters/")


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RatingIn(BaseModel):
    value: int = Field(ge=1, le=5)


class GenreIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def supported_genre(cls, value: str) -> str:
        normalized = value.strip()
        for name in GENRE_NAMES:
            if normalized.casefold() == name.casefold():
                return name
        raise ValueError("Genre must be one of the supported catalog genres")


class EmailChangeIn(BaseModel):
    email: EmailStr


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class AccountDeleteIn(BaseModel):
    password: str
    confirmation: str


class MovieIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    year: int = Field(ge=1888, le=2200)
    overview: str = ""
    keywords: str = ""
    poster_url: str | None = Field(default=None, max_length=1000)
    external_id: str | None = None
    genre_ids: list[int] = []
    actors: list[str] = []
    directors: list[str] = []

    @field_validator("poster_url")
    @classmethod
    def poster_url_rule(cls, value: str | None) -> str | None:
        return validate_poster_url(value)


class MoviePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    year: int | None = Field(default=None, ge=1888, le=2200)
    overview: str | None = None
    keywords: str | None = None
    poster_url: str | None = Field(default=None, max_length=1000)
    external_id: str | None = None
    genre_ids: list[int] | None = None
    actors: list[str] | None = None
    directors: list[str] | None = None

    @field_validator("poster_url")
    @classmethod
    def poster_url_rule(cls, value: str | None) -> str | None:
        return validate_poster_url(value)
