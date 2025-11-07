"""Database initialization and session management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from src.utils.config import get_settings
from src.web.models import Base

settings = get_settings()

# Create engine
engine = create_engine(
    f"sqlite:///{settings.database_path}",
    connect_args={"check_same_thread": False},  # Needed for SQLite
    echo=False,
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """
    Get database session.
    
    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

