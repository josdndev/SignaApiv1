from __future__ import annotations

import os
from functools import lru_cache
from typing import Generator

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine


DEFAULT_SQLITE_URL = "sqlite:///./saas.db"


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def get_database_url() -> str:
    return _normalize_database_url(
        os.getenv("SAAS_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or DEFAULT_SQLITE_URL
    )


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    database_url = get_database_url()
    if database_url.startswith("sqlite"):
        return create_engine(database_url, connect_args={"check_same_thread": False})
    return create_engine(database_url, pool_pre_ping=True)


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session


def init_db() -> None:
    # Importing the models registers the tables on SQLModel.metadata.
    from . import models_saas  # noqa: F401

    SQLModel.metadata.create_all(get_engine())

