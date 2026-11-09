from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Cluck Club API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://cluck:cluck@db:5432/cluckclub"
    jwt_secret_key: SecretStr
    redemption_qr_secret_key: SecretStr | None = None
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    business_timezone: str = "Asia/Kolkata"
    redemption_qr_ttl_minutes: int = 15
    development_spin_limit: int = 1
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

    @field_validator("redemption_qr_secret_key")
    @classmethod
    def validate_redemption_qr_secret(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and len(value.get_secret_value()) < 32:
            raise ValueError("REDEMPTION_QR_SECRET_KEY must contain at least 32 characters")
        return value

    @field_validator("business_timezone")
    @classmethod
    def validate_business_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("BUSINESS_TIMEZONE must be a valid IANA timezone") from exc
        return value

    @field_validator("redemption_qr_ttl_minutes")
    @classmethod
    def validate_redemption_qr_ttl(cls, value: int) -> int:
        if not 5 <= value <= 60:
            raise ValueError("REDEMPTION_QR_TTL_MINUTES must be between 5 and 60")
        return value

    @field_validator("development_spin_limit")
    @classmethod
    def validate_development_spin_limit(cls, value: int) -> int:
        if not 1 <= value <= 100:
            raise ValueError("DEVELOPMENT_SPIN_LIMIT must be between 1 and 100")
        return value

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.environment.lower() != "production":
            return self
        if not self.cookie_secure:
            raise ValueError("COOKIE_SECURE must be true in production")
        if self.redemption_qr_secret_key is None:
            raise ValueError("REDEMPTION_QR_SECRET_KEY must be set in production")
        if self.redemption_qr_secret_key == self.jwt_secret_key:
            raise ValueError("REDEMPTION_QR_SECRET_KEY must be separate from JWT_SECRET_KEY")
        for secret in (self.jwt_secret_key, self.redemption_qr_secret_key):
            normalized_secret = secret.get_secret_value().lower().replace("_", "-")
            if any(marker in normalized_secret for marker in ("change-me", "replace-me", "local-development")):
                raise ValueError("Production secrets must not contain example placeholder values")
        if not self.rate_limit_storage_uri.startswith(("redis://", "rediss://")):
            raise ValueError("RATE_LIMIT_STORAGE_URI must use Redis in production")
        if self.development_spin_limit != 1:
            raise ValueError("DEVELOPMENT_SPIN_LIMIT must be 1 in production")
        if not self.cors_origins or "*" in self.cors_origins:
            raise ValueError("CORS_ORIGINS_RAW must contain explicit production origins")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]


settings = Settings()
