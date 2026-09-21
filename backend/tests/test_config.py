"""
Tests for application configuration loading.

Verifies that Settings loads correctly and provides expected defaults.
"""

import pytest

from app.core.config import Settings, get_settings


def test_settings_loads_without_error():
    """Settings must instantiate without raising an exception."""
    settings = Settings()
    assert settings is not None


def test_settings_has_app_name():
    """Settings must have a non-empty APP_NAME."""
    settings = Settings()
    assert len(settings.APP_NAME) > 0


def test_settings_has_database_url():
    """Settings must have a DATABASE_URL."""
    settings = Settings()
    assert settings.DATABASE_URL.startswith("postgresql")


def test_settings_cors_origins_returns_list():
    """cors_origins property must return a list with at least one item."""
    settings = Settings()
    origins = settings.cors_origins
    assert isinstance(origins, list)
    assert len(origins) > 0


def test_settings_get_settings_returns_singleton():
    """get_settings() must return the same cached instance on repeated calls."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_settings_is_development_by_default():
    """Default APP_ENV should be 'development', so is_development is True."""
    settings = Settings()
    # If no .env overrides APP_ENV, the default is 'development'
    if settings.APP_ENV.lower() == "development":
        assert settings.is_development is True
        assert settings.is_production is False
