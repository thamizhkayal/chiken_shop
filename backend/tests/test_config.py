import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings


def production_settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "environment": "production",
        "jwt_secret_key": SecretStr("j" * 48),
        "redemption_qr_secret_key": SecretStr("r" * 48),
        "cookie_secure": True,
        "rate_limit_storage_uri": "redis://redis:6379/0",
        "development_spin_limit": 1,
        "cors_origins_raw": "https://loyalty.example.com",
    }
    return Settings(**(values | overrides))


def test_production_settings_accept_secure_configuration():
    settings = production_settings()

    assert settings.cookie_secure is True
    assert settings.rate_limit_storage_uri.startswith("redis://")


@pytest.mark.parametrize(
    "overrides",
    [
        {"cookie_secure": False},
        {"redemption_qr_secret_key": None},
        {"redemption_qr_secret_key": SecretStr("j" * 48)},
        {"jwt_secret_key": SecretStr("CHANGE_ME_GENERATE_A_RANDOM_32_BYTE_SECRET")},
        {"rate_limit_storage_uri": "memory://"},
        {"development_spin_limit": 10},
        {"cors_origins_raw": "*"},
    ],
)
def test_production_settings_reject_insecure_configuration(overrides):
    with pytest.raises(ValidationError):
        production_settings(**overrides)
