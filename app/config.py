from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "sap_middleware"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"

    # SAP RFC
    sap_mock_mode: bool = True
    sap_ashost: str = ""
    sap_sysnr: str = "00"
    sap_client: str = "100"
    sap_user: str = ""
    sap_passwd: str = ""
    sap_lang: str = "EN"
    sap_pool_size: int = 2

    # API
    api_key: str = "change-me"
    log_level: str = "INFO"

    # Scheduler
    sync_interval_minutes: int = 0

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
