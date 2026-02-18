"""Storage abstraction layer for S3-compatible storage."""

from src.storage.s3_storage import S3Storage, get_storage

__all__ = ['S3Storage', 'get_storage']
