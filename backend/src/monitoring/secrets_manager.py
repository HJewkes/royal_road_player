"""AWS Secrets Manager integration for credential management (LocalStack or AWS)."""

import json
import logging
import os
from typing import Optional, Dict, Any
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

logger = logging.getLogger(__name__)


class SecretsManager:
    """AWS Secrets Manager client for LocalStack (dev) and AWS (prod)."""
    
    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region_name: str = "us-east-1",
    ):
        """
        Initialize Secrets Manager client.
        
        Args:
            endpoint_url: Custom endpoint URL (for LocalStack)
            aws_access_key_id: AWS access key
            aws_secret_access_key: AWS secret key
            region_name: AWS region
        """
        self.endpoint_url = endpoint_url
        
        # Get credentials
        self.aws_access_key_id = aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID", "test")
        self.aws_secret_access_key = aws_secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY", "test")
        self.region_name = region_name
        
        # Create Secrets Manager client
        config = Config(
            retries={'max_attempts': 3, 'mode': 'standard'}
        )
        
        self.secrets_client = boto3.client(
            'secretsmanager',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name,
            config=config,
        )
    
    def get_secret(self, secret_name: str) -> Optional[Dict[str, Any]]:
        """
        Get secret value from Secrets Manager.
        
        Args:
            secret_name: Secret name or ARN
            
        Returns:
            Secret value as dictionary, or None if not found
        """
        try:
            response = self.secrets_client.get_secret_value(SecretId=secret_name)
            secret_string = response.get('SecretString', '')
            
            # Try to parse as JSON
            try:
                return json.loads(secret_string)
            except json.JSONDecodeError:
                # Return as plain string
                return {'value': secret_string}
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == 'ResourceNotFoundException':
                logger.warning(f"Secret '{secret_name}' not found")
                return None
            logger.error(f"Failed to get secret '{secret_name}': {e}")
            return None
    
    def create_secret(
        self,
        secret_name: str,
        secret_value: Dict[str, Any],
        description: Optional[str] = None,
    ) -> bool:
        """
        Create or update secret in Secrets Manager.
        
        Args:
            secret_name: Secret name
            secret_value: Secret value as dictionary
            description: Optional description
            
        Returns:
            True if successful, False otherwise
        """
        try:
            secret_string = json.dumps(secret_value)
            
            # Try to create
            try:
                self.secrets_client.create_secret(
                    Name=secret_name,
                    SecretString=secret_string,
                    Description=description or f"Secret for {secret_name}",
                )
                logger.info(f"✅ Created secret '{secret_name}'")
                return True
            except ClientError as e:
                if e.response.get('Error', {}).get('Code') == 'ResourceExistsException':
                    # Update existing secret
                    self.secrets_client.update_secret(
                        SecretId=secret_name,
                        SecretString=secret_string,
                    )
                    logger.info(f"✅ Updated secret '{secret_name}'")
                    return True
                raise
        except Exception as e:
            logger.error(f"Failed to create/update secret '{secret_name}': {e}")
            return False
    
    def delete_secret(self, secret_name: str, force: bool = False) -> bool:
        """
        Delete secret from Secrets Manager.
        
        Args:
            secret_name: Secret name or ARN
            force: Force deletion without recovery window
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if force:
                self.secrets_client.delete_secret(
                    SecretId=secret_name,
                    ForceDeleteWithoutRecovery=True,
                )
            else:
                self.secrets_client.delete_secret(SecretId=secret_name)
            logger.info(f"✅ Deleted secret '{secret_name}'")
            return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == 'ResourceNotFoundException':
                logger.warning(f"Secret '{secret_name}' not found")
                return True  # Already deleted
            logger.error(f"Failed to delete secret '{secret_name}': {e}")
            return False


def get_secrets_manager() -> Optional[SecretsManager]:
    """
    Get or create Secrets Manager instance.
    
    Returns:
        SecretsManager instance or None if not enabled
    """
    from src.utils.config import get_settings
    settings = get_settings()
    
    if not settings.use_secrets_manager:
        return None
    
    return SecretsManager(
        endpoint_url=settings.secrets_manager_endpoint_url,
    )
