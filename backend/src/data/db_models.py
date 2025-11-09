"""SQLAlchemy database models."""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import relationship

from src.data.database import Base
from src.models.enums import ChunkStatus


class BookDB(Base):
    """Book table in database."""
    __tablename__ = "books"
    
    id = Column(String, primary_key=True)  # book_id
    title = Column(String, nullable=False)
    author = Column(String, nullable=True)
    url = Column(String, nullable=True)
    filter_book_number = Column(Integer, nullable=True)
    path = Column(String, nullable=True)  # Book directory path
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    chapters = relationship("ChapterDB", back_populates="book", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_books_path', 'path'),
    )


class ChapterDB(Base):
    """Chapter table in database."""
    __tablename__ = "chapters"
    
    id = Column(String, primary_key=True)  # chapter_id (book_id_chapter_number)
    book_id = Column(String, ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_number = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    number = Column(Integer, nullable=True)  # Royal Road chapter number
    url = Column(String, nullable=True)
    path = Column(String, nullable=True)  # Chapter directory path
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    book = relationship("BookDB", back_populates="chapters")
    chunks = relationship("ChunkDB", back_populates="chapter", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_chapters_book_number', 'book_id', 'chapter_number'),
        Index('idx_chapters_path', 'path'),
    )


class ChunkDB(Base):
    """Chunk table in database."""
    __tablename__ = "chunks"
    
    id = Column(String, primary_key=True)  # chunk_id (book_id_chapter_number_index)
    book_id = Column(String, nullable=False, index=True)
    chapter_id = Column(String, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_number = Column(Integer, nullable=False, index=True)
    index = Column(Integer, nullable=False)  # Chunk index within chapter
    text_start = Column(Integer, nullable=False)
    text_end = Column(Integer, nullable=False)
    status = Column(String, nullable=False, index=True)  # ChunkStatus enum value
    path = Column(String, nullable=True)  # Chunk directory path
    
    # Audio metadata
    generation_time_seconds = Column(Float, nullable=True)
    audio_duration_seconds = Column(Float, nullable=True)
    
    # TTS synthesis parameters
    voice_name = Column(String, nullable=True)
    speed = Column(Float, nullable=True)
    
    # Post-processing
    pre_pause_ms = Column(Integer, default=0)
    post_pause_ms = Column(Integer, default=0)
    
    # Text analysis hints
    is_dialogue = Column(Boolean, default=False)
    is_scene_break = Column(Boolean, default=False)
    
    # Error tracking
    error = Column(String, nullable=True)  # Error message if generation failed
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    processing_started_at = Column(DateTime, nullable=True)  # When processing started (for recovery)
    
    # Relationships
    chapter = relationship("ChapterDB", back_populates="chunks")
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_chunks_book_chapter', 'book_id', 'chapter_number'),
        Index('idx_chunks_status', 'status'),
        Index('idx_chunks_chapter_index', 'chapter_id', 'index'),
        Index('idx_chunks_path', 'path'),
    )

