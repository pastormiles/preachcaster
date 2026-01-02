from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "PreachCaster"
    debug: bool = False

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/preachcaster"

    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Google/YouTube
    google_client_id: str = ""
    google_client_secret: str = ""

    # OpenAI
    openai_api_key: str = ""

    # Google Cloud Storage
    gcs_project_id: str = ""
    gcs_bucket_name: str = "preachcaster-audio"

    # Redis
    redis_url: str = "redis://localhost:6379"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
