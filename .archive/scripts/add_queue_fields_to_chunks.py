"""Migration script to add error and processing_started_at fields to chunks table."""

import logging
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from src.data.database import get_engine, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate():
    """Add error and processing_started_at columns to chunks table."""
    engine = get_engine()
    
    with engine.connect() as conn:
        # Check if columns already exist
        result = conn.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='chunks'
        """))
        if not result.fetchone():
            logger.error("chunks table does not exist. Run init_db() first.")
            return False
        
        # Check if error column exists
        result = conn.execute(text("PRAGMA table_info(chunks)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'error' not in columns:
            logger.info("Adding 'error' column to chunks table...")
            conn.execute(text("ALTER TABLE chunks ADD COLUMN error VARCHAR"))
            conn.commit()
            logger.info("✅ Added 'error' column")
        else:
            logger.info("'error' column already exists")
        
        if 'processing_started_at' not in columns:
            logger.info("Adding 'processing_started_at' column to chunks table...")
            conn.execute(text("ALTER TABLE chunks ADD COLUMN processing_started_at DATETIME"))
            conn.commit()
            logger.info("✅ Added 'processing_started_at' column")
        else:
            logger.info("'processing_started_at' column already exists")
    
    logger.info("✅ Migration complete")
    return True


if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        sys.exit(1)

