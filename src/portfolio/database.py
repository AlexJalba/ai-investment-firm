"""SQLite-backed portfolio persistence — crash-safe with WAL mode."""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.portfolio.models import Base

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def _enable_wal(dbapi_conn, _):
    """Enable WAL journal mode so reads don't block writes."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_engine(db_path: str = "./data/portfolio.db") -> Engine:
    global _engine
    if _engine is not None:
        return _engine
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    event.listen(_engine, "connect", _enable_wal)
    Base.metadata.create_all(_engine)
    return _engine


def get_session(db_path: str = "./data/portfolio.db") -> Session:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(db_path), autocommit=False, autoflush=False)
    return _SessionLocal()
