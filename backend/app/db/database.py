import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings
from app.core.logging import logger


def get_engine():
    if settings.DATABASE_URL.startswith("postgresql"):
        engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            connect_args={"connect_timeout": 10}
        )
        return engine

    if os.environ.get("VERCEL"):
        import shutil
        tmp_db = "/tmp/tender_intelligence.db"
        orig_db = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "tender_intelligence.db"))
        if os.path.exists(orig_db) and not os.path.exists(tmp_db):
            try:
                shutil.copy2(orig_db, tmp_db)
            except Exception as e:
                logger.warning(f"Could not copy seed SQLite db to /tmp: {e}")
        sqlite_path = tmp_db
    else:
        sqlite_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "tender_intelligence.db"))

    return create_engine(
        f"sqlite:///{sqlite_path}",
        connect_args={"check_same_thread": False}
    )

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db() -> Generator:
    """FastAPI Dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
