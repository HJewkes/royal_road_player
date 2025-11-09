"""Database connection and session management."""

import logging
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import StaticPool

from src.utils.config import get_settings

logger = logging.getLogger(__name__)

# Base class for declarative models
Base = declarative_base()

# Import models to register them with SQLAlchemy
from src.data.db_models import BookDB, ChapterDB, ChunkDB  # noqa: E402, F401

# Global engine and session factory
_engine = None
_SessionLocal = None


def get_engine():
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        database_path = Path(settings.database_path)
        database_path.parent.mkdir(parents=True, exist_ok=True)
        
        # SQLite connection string
        database_url = f"sqlite:///{database_path}"
        
        # Create engine with connection pooling optimized for SQLite
        _engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},  # Allow multi-threaded access
            poolclass=StaticPool,  # SQLite doesn't need connection pooling
            echo=False,  # Set to True for SQL query logging
        )
        
        # Enable foreign keys for SQLite
        @event.listens_for(_engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        
        logger.info(f"Database engine created: {database_url}")
    
    return _engine


def get_session() -> Session:
    """Get a database session."""
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    return _SessionLocal()


def init_db():
    """Initialize the database (create tables)."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")


def close_db():
    """Close database connections."""
    global _engine
    if _engine:
        _engine.dispose()
        _engine = None
        logger.info("Database connections closed")

