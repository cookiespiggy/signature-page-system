"""SQLite 数据库连接与会话管理。"""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/junhe.db")


def _ensure_sqlite_directory(url: str) -> None:
    if not url.startswith("sqlite"):
        return
    db_path = url.replace("sqlite:///", "", 1)
    if db_path in (":memory:", ""):
        return
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_directory(DATABASE_URL)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    if DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类。"""


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入用的数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
