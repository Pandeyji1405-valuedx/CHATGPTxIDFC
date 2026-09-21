"""
SQLAlchemy declarative base and shared model utilities.

All ORM models should inherit from the `Base` class defined here.
This ensures Alembic can auto-detect and manage migrations for every model.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Project-wide SQLAlchemy declarative base.

    All ORM model classes must inherit from this class.
    Do not use `declarative_base()` anywhere else in the project.

    Usage::

        from app.db.base import Base

        class SomeModel(Base):
            __tablename__ = "some_table"
            ...
    """

    pass
