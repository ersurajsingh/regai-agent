import sys
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Gemini
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-flash-latest"

    # MongoDB
    MONGODB_URI: str
    MONGODB_DB_NAME: str = "regai"

    # Phoenix
    PHOENIX_COLLECTOR_ENDPOINT: str = "http://localhost:4317"

    # App
    APP_ENV: str = "development"
    SECRET_KEY: str
    SESSION_EXPIRE_HOURS: int = 24
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]


def _load_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except Exception as e:
        print(f"[RegAI] Missing required environment variable: {e}")
        sys.exit(1)


settings = _load_settings()
