"""Hybrid storage that uses S3 when enabled, falls back to local filesystem."""

import logging
from pathlib import Path
from typing import Optional

from src.utils.config import get_settings

logger = logging.getLogger(__name__)


class HybridStorage:
    """Storage abstraction that uses S3 or local filesystem based on configuration."""
    
    def __init__(self):
        """Initialize hybrid storage."""
        self.settings = get_settings()
        self._s3_storage = None
        
        if self.settings.s3_use_storage:
            try:
                from src.storage.s3_storage import get_storage
                self._s3_storage = get_storage()
                logger.info("Using S3 storage")
            except Exception as e:
                logger.warning(f"Failed to initialize S3 storage, falling back to local: {e}")
                self._s3_storage = None
        else:
            logger.info("Using local filesystem storage")
    
    def _get_s3_key(self, file_path: Path) -> str:
        """
        Convert local file path to S3 key.
        
        Args:
            file_path: Local file path
            
        Returns:
            S3 key (path)
        """
        # Remove leading data/ prefix if present
        path_str = str(file_path)
        if path_str.startswith('data/'):
            path_str = path_str[5:]  # Remove 'data/'
        elif path_str.startswith('/app/data/'):
            path_str = path_str[10:]  # Remove '/app/data/'
        
        # Normalize path separators
        return path_str.replace('\\', '/')
    
    def read_file(self, file_path: Path) -> Optional[bytes]:
        """
        Read file from storage (S3 or local).
        
        Args:
            file_path: File path
            
        Returns:
            File content as bytes, or None if not found
        """
        if self._s3_storage:
            key = self._get_s3_key(file_path)
            return self._s3_storage.get_object(key)
        else:
            # Local filesystem
            if not file_path.exists():
                return None
            try:
                return file_path.read_bytes()
            except Exception as e:
                logger.error(f"Failed to read file {file_path}: {e}")
                return None
    
    def write_file(self, file_path: Path, data: bytes, content_type: Optional[str] = None) -> bool:
        """
        Write file to storage (S3 or local).
        
        Args:
            file_path: File path
            data: File content as bytes
            content_type: Optional content type
            
        Returns:
            True if successful, False otherwise
        """
        if self._s3_storage:
            key = self._get_s3_key(file_path)
            return self._s3_storage.put_object(key, data, content_type=content_type)
        else:
            # Local filesystem
            try:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_bytes(data)
                return True
            except Exception as e:
                logger.error(f"Failed to write file {file_path}: {e}")
                return False
    
    def file_exists(self, file_path: Path) -> bool:
        """
        Check if file exists in storage.
        
        Args:
            file_path: File path
            
        Returns:
            True if file exists, False otherwise
        """
        if self._s3_storage:
            key = self._get_s3_key(file_path)
            return self._s3_storage.object_exists(key)
        else:
            return file_path.exists()
    
    def delete_file(self, file_path: Path) -> bool:
        """
        Delete file from storage.
        
        Args:
            file_path: File path
            
        Returns:
            True if successful, False otherwise
        """
        if self._s3_storage:
            key = self._get_s3_key(file_path)
            return self._s3_storage.delete_object(key)
        else:
            try:
                if file_path.exists():
                    file_path.unlink()
                return True
            except Exception as e:
                logger.error(f"Failed to delete file {file_path}: {e}")
                return False
    
    def get_file_url(self, file_path: Path, expires_in: int = 3600) -> Optional[str]:
        """
        Get URL for file access (presigned URL for S3, local path for filesystem).
        
        Args:
            file_path: File path
            expires_in: URL expiration in seconds (for S3)
            
        Returns:
            URL string or None
        """
        if self._s3_storage:
            key = self._get_s3_key(file_path)
            return self._s3_storage.get_object_url(key, expires_in=expires_in)
        else:
            # For local filesystem, return relative path
            # This will be served by FastAPI static file mount
            return str(file_path)


# Global hybrid storage instance
_hybrid_storage_instance: Optional[HybridStorage] = None


def get_file_storage() -> HybridStorage:
    """
    Get hybrid storage instance (singleton).
    
    Returns:
        HybridStorage instance
    """
    global _hybrid_storage_instance
    if _hybrid_storage_instance is None:
        _hybrid_storage_instance = HybridStorage()
    return _hybrid_storage_instance
