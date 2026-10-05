from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_title: str = "Oil Data Back"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "oil_data"
    postgres_user: str = "oil_data"
    postgres_password: str = ""
    marts_dir: Path = Path("data/marts")
    # Comma-separated browser origins allowed to read the API (the static site).
    cors_origins: str = (
        "http://localhost:8080,http://127.0.0.1:8080,https://glec1er.github.io"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
DATABASE_URL = settings.database_url
