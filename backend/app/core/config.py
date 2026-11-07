from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Cluck Club API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://cluck:cluck@db:5432/cluckclub"
    jwt_secret_key: SecretStr
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    business_timezone: str = "Asia/Kolkata"
    cookie_secure: bool = False
    cookie_domain: str | None = None
    cors_origins_raw: str = "http://localhost:3000"
    rate_limit_storage_uri: str = "memory://"

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_secret_length(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET_KEY must contain at least 32 characters")
        return value

    @field_validator("business_timezone")
    @classmethod
    def validate_business_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("BUSINESS_TIMEZONE must be a valid IANA timezone") from exc
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]


settings = Settings()
