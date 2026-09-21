"""
Alembic environment configuration.

This file is invoked by Alembic CLI commands (migrate, upgrade, downgrade).
It wires Alembic to:
  1. The project's SQLAlchemy declarative Base (for autogenerate support)
  2. The DATABASE_SYNC_URL environment variable (no hardcoded credentials)

Run migrations:
    alembic upgrade head

Generate a new migration:
    alembic revision --autogenerate -m "describe your change"
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# ------------------------------------------------------------------ #
# Ensure the project root is on sys.path so `app.*` imports work
# ------------------------------------------------------------------ #
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ------------------------------------------------------------------ #
# Import application models so Alembic can detect schema changes
# ------------------------------------------------------------------ #
# This import causes all model classes to register with Base.metadata.
# Add new model imports to app/models/__init__.py, NOT here.
from app.core.config import get_settings
from app.models import Base  # noqa: E402

# ------------------------------------------------------------------ #
# Alembic Config object — provides access to alembic.ini values
# ------------------------------------------------------------------ #
config = context.config

# Override sqlalchemy.url with the environment variable or .env file
settings = get_settings()
database_sync_url = os.environ.get("DATABASE_SYNC_URL") or settings.DATABASE_SYNC_URL
if database_sync_url:
    config.set_main_option("sqlalchemy.url", database_sync_url)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate support
target_metadata = Base.metadata


# ------------------------------------------------------------------ #
# Migration modes
# ------------------------------------------------------------------ #
def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Generates SQL scripts without connecting to the database.
    Useful for producing migration scripts to review before applying.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    Creates a real database connection and applies migrations directly.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
