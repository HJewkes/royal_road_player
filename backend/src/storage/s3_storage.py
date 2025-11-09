"""S3-compatible storage abstraction for LocalStack (dev) and AWS S3 (prod)."""

import logging
import os
from io import BytesIO
from pathlib import Path
from typing import Optional, BinaryIO, List
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.config import Config

logger = logging.getLogger(__name__)


class S3Storage:
    """S3-compatible storage client for LocalStack (dev) and AWS S3 (prod)."""
    
    def __init__(
        self,
        bucket_name: str,
        endpoint_url: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region_name: str = "us-east-1",
    ):
        """
        Initialize S3 storage client.
        
        Args:
            bucket_name: S3 bucket name
            endpoint_url: Custom endpoint URL (for LocalStack: http://localstack:4566)
            aws_access_key_id: AWS access key (optional, uses env vars if not provided)
            aws_secret_access_key: AWS secret key (optional, uses env vars if not provided)
            region_name: AWS region (default: us-east-1)
        """
        self.bucket_name = bucket_name
        self.endpoint_url = endpoint_url
        
        # Get credentials from parameters or environment
        self.aws_access_key_id = aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID", "test")
        self.aws_secret_access_key = aws_secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY", "test")
        self.region_name = region_name
        
        # Create S3 client
        config = Config(
            signature_version='s3v4',
            retries={'max_attempts': 3, 'mode': 'standard'}
        )
        
        self.s3_client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name,
            config=config,
        )
        
        # Ensure bucket exists
        self._ensure_bucket()
    
    def _ensure_bucket(self) -> None:
        """Ensure bucket exists, create if it doesn't."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.debug(f"Bucket '{self.bucket_name}' exists")
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == '404':
                # Bucket doesn't exist, create it
                try:
                    if self.endpoint_url:
                        # LocalStack - no location constraint needed
                        self.s3_client.create_bucket(Bucket=self.bucket_name)
                    else:
                        # Real S3 - may need location constraint
                        self.s3_client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': self.region_name}
                        )
                    logger.info(f"✅ Created bucket '{self.bucket_name}'")
                except ClientError as create_error:
                    logger.error(f"Failed to create bucket '{self.bucket_name}': {create_error}")
                    raise
            else:
                logger.error(f"Error checking bucket '{self.bucket_name}': {e}")
                raise
    
    def put_object(
        self,
        key: str,
        data: bytes,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
        """
        Upload object to S3.
        
        Args:
            key: Object key (path)
            data: Object data as bytes
            content_type: Optional content type (e.g., 'text/plain', 'audio/wav')
            metadata: Optional metadata dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            if metadata:
                extra_args['Metadata'] = metadata
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=data,
                **extra_args
            )
            logger.debug(f"Uploaded object: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to upload object {key}: {e}")
            return False
    
    def get_object(self, key: str) -> Optional[bytes]:
        """
        Download object from S3.
        
        Args:
            key: Object key (path)
            
        Returns:
            Object data as bytes, or None if not found
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return response['Body'].read()
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == 'NoSuchKey':
                logger.debug(f"Object not found: {key}")
                return None
            logger.error(f"Failed to download object {key}: {e}")
            return None
    
    def delete_object(self, key: str) -> bool:
        """
        Delete object from S3.
        
        Args:
            key: Object key (path)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            logger.debug(f"Deleted object: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete object {key}: {e}")
            return False
    
    def object_exists(self, key: str) -> bool:
        """
        Check if object exists in S3.
        
        Args:
            key: Object key (path)
            
        Returns:
            True if object exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == '404':
                return False
            logger.error(f"Error checking object {key}: {e}")
            return False
    
    def list_objects(self, prefix: str = "", max_keys: int = 1000) -> List[str]:
        """
        List objects in bucket with given prefix.
        
        Args:
            prefix: Key prefix to filter by
            max_keys: Maximum number of keys to return
            
        Returns:
            List of object keys
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            
            if 'Contents' not in response:
                return []
            
            return [obj['Key'] for obj in response['Contents']]
        except Exception as e:
            logger.error(f"Failed to list objects with prefix '{prefix}': {e}")
            return []
    
    def get_object_url(self, key: str, expires_in: int = 3600) -> Optional[str]:
        """
        Generate presigned URL for object access.
        
        Args:
            key: Object key (path)
            expires_in: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Presigned URL or None if failed
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expires_in
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL for {key}: {e}")
            return None
    
    def upload_file(
        self,
        file_path: Path,
        key: str,
        content_type: Optional[str] = None,
    ) -> bool:
        """
        Upload file from local filesystem to S3.
        
        Args:
            file_path: Local file path
            key: S3 object key (path)
            content_type: Optional content type
            
        Returns:
            True if successful, False otherwise
        """
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            
            self.s3_client.upload_file(
                str(file_path),
                self.bucket_name,
                key,
                ExtraArgs=extra_args
            )
            logger.debug(f"Uploaded file {file_path} to {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to upload file {file_path} to {key}: {e}")
            return False
    
    def download_file(
        self,
        key: str,
        file_path: Path,
    ) -> bool:
        """
        Download file from S3 to local filesystem.
        
        Args:
            key: S3 object key (path)
            file_path: Local file path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            self.s3_client.download_file(
                self.bucket_name,
                key,
                str(file_path)
            )
            logger.debug(f"Downloaded {key} to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to download {key} to {file_path}: {e}")
            return False


# Global storage instance
_storage_instance: Optional[S3Storage] = None


def get_storage() -> S3Storage:
    """
    Get or create S3 storage instance (singleton).
    
    Returns:
        S3Storage instance
    """
    global _storage_instance
    if _storage_instance is None:
        from src.utils.config import get_settings
        settings = get_settings()
        
        _storage_instance = S3Storage(
            bucket_name=settings.s3_bucket_name,
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region_name,
        )
        logger.info(f"Initialized S3 storage: bucket={settings.s3_bucket_name}, endpoint={settings.s3_endpoint_url or 'AWS S3'}")
    
    return _storage_instance
