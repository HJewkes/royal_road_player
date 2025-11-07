"""Database models."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Book(Base):
    """Book model."""

    __tablename__ = "books"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    author = Column(String)
    url = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Chapter(Base):
    """Chapter model."""

    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    book_id = Column(String, nullable=False, index=True)
    chapter_number = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    text_path = Column(String)
    audio_path = Column(String)
    annotation_path = Column(String)
    duration_seconds = Column(Float)
    word_count = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


class Progress(Base):
    """Playback progress model."""

    __tablename__ = "progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    book_id = Column(String, nullable=False, index=True)
    chapter_id = Column(Integer, nullable=False)
    position_seconds = Column(Float, default=0.0)
    completed = Column(Integer, default=0)  # 0 = not completed, 1 = completed
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

