"""SQS-compatible queue for job processing (LocalStack or AWS SQS)."""

import json
import logging
import os
from typing import Optional, List, Dict, Any
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

from src.storage.s3_storage import S3Storage  # Reuse S3Storage config pattern

logger = logging.getLogger(__name__)


class SQSQueue:
    """SQS-compatible queue client for LocalStack (dev) and AWS SQS (prod)."""
    
    def __init__(
        self,
        queue_name: str,
        endpoint_url: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region_name: str = "us-east-1",
    ):
        """
        Initialize SQS queue client.
        
        Args:
            queue_name: SQS queue name
            endpoint_url: Custom endpoint URL (for LocalStack: http://localstack:4566)
            aws_access_key_id: AWS access key (optional, uses env vars if not provided)
            aws_secret_access_key: AWS secret key (optional, uses env vars if not provided)
            region_name: AWS region (default: us-east-1)
        """
        self.queue_name = queue_name
        self.endpoint_url = endpoint_url
        
        # Get credentials from parameters or environment
        self.aws_access_key_id = aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID", "test")
        self.aws_secret_access_key = aws_secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY", "test")
        self.region_name = region_name
        
        # Create SQS client
        config = Config(
            retries={'max_attempts': 3, 'mode': 'standard'}
        )
        
        self.sqs_client = boto3.client(
            'sqs',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name,
            config=config,
        )
        
        # Get or create queue URL
        self.queue_url = self._ensure_queue()
    
    def _ensure_queue(self) -> str:
        """Ensure queue exists, create if it doesn't. Returns queue URL."""
        try:
            # Try to get queue URL
            response = self.sqs_client.get_queue_url(QueueName=self.queue_name)
            queue_url = response['QueueUrl']
            logger.debug(f"Queue '{self.queue_name}' exists: {queue_url}")
            return queue_url
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == 'AWS.SimpleQueueService.NonExistentQueue':
                # Queue doesn't exist, create it
                try:
                    response = self.sqs_client.create_queue(
                        QueueName=self.queue_name,
                        Attributes={
                            'VisibilityTimeout': '300',  # 5 minutes
                            'MessageRetentionPeriod': '1209600',  # 14 days
                            'ReceiveMessageWaitTimeSeconds': '20',  # Long polling
                        }
                    )
                    queue_url = response['QueueUrl']
                    logger.info(f"✅ Created queue '{self.queue_name}': {queue_url}")
                    return queue_url
                except ClientError as create_error:
                    logger.error(f"Failed to create queue '{self.queue_name}': {create_error}")
                    raise
            else:
                logger.error(f"Error checking queue '{self.queue_name}': {e}")
                raise
    
    def send_message(self, message_body: Dict[str, Any], delay_seconds: int = 0) -> bool:
        """
        Send message to queue.
        
        Args:
            message_body: Message body as dictionary (will be JSON serialized)
            delay_seconds: Optional delay before message becomes visible (0-900)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(message_body),
                DelaySeconds=delay_seconds,
            )
            logger.debug(f"Sent message to queue: {response.get('MessageId')}")
            return True
        except Exception as e:
            logger.error(f"Failed to send message to queue: {e}")
            return False
    
    def receive_messages(
        self,
        max_messages: int = 1,
        wait_time_seconds: int = 20,
        visibility_timeout: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Receive messages from queue.
        
        Args:
            max_messages: Maximum number of messages to receive (1-10)
            wait_time_seconds: Long polling wait time (0-20)
            visibility_timeout: Optional visibility timeout override
            
        Returns:
            List of messages with 'Body', 'ReceiptHandle', 'MessageId', etc.
        """
        try:
            receive_params = {
                'QueueUrl': self.queue_url,
                'MaxNumberOfMessages': min(max_messages, 10),
                'WaitTimeSeconds': wait_time_seconds,
            }
            if visibility_timeout:
                receive_params['VisibilityTimeout'] = visibility_timeout
            
            response = self.sqs_client.receive_message(**receive_params)
            
            messages = []
            for msg in response.get('Messages', []):
                try:
                    body = json.loads(msg['Body'])
                    messages.append({
                        'Body': body,
                        'ReceiptHandle': msg['ReceiptHandle'],
                        'MessageId': msg['MessageId'],
                        'Attributes': msg.get('Attributes', {}),
                    })
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse message body: {msg.get('Body')}")
            
            return messages
        except Exception as e:
            logger.error(f"Failed to receive messages from queue: {e}")
            return []
    
    def delete_message(self, receipt_handle: str) -> bool:
        """
        Delete message from queue (acknowledge processing).
        
        Args:
            receipt_handle: Receipt handle from received message
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.sqs_client.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle,
            )
            logger.debug("Deleted message from queue")
            return True
        except Exception as e:
            logger.error(f"Failed to delete message from queue: {e}")
            return False
    
    def get_queue_attributes(self) -> Dict[str, Any]:
        """
        Get queue attributes (approximate number of messages, etc.).
        
        Returns:
            Dictionary of queue attributes
        """
        try:
            response = self.sqs_client.get_queue_attributes(
                QueueUrl=self.queue_url,
                AttributeNames=['All']
            )
            return response.get('Attributes', {})
        except Exception as e:
            logger.error(f"Failed to get queue attributes: {e}")
            return {}
    
    def purge_queue(self) -> bool:
        """
        Purge all messages from queue.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.sqs_client.purge_queue(QueueUrl=self.queue_url)
            logger.info(f"Purged queue '{self.queue_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to purge queue: {e}")
            return False


# Global queue instance
_queue_instance: Optional[SQSQueue] = None


def get_sqs_queue() -> Optional[SQSQueue]:
    """
    Get or create SQS queue instance (singleton).
    
    Returns:
        SQSQueue instance or None if SQS is not enabled
    """
    global _queue_instance
    if _queue_instance is None:
        from src.utils.config import get_settings
        settings = get_settings()
        
        if not settings.sqs_use_queue:
            return None
        
        _queue_instance = SQSQueue(
            queue_name=settings.sqs_queue_name,
            endpoint_url=settings.sqs_endpoint_url,
            aws_access_key_id=settings.sqs_access_key_id,
            aws_secret_access_key=settings.sqs_secret_access_key,
            region_name=settings.sqs_region_name,
        )
        logger.info(f"Initialized SQS queue: queue={settings.sqs_queue_name}, endpoint={settings.sqs_endpoint_url or 'AWS SQS'}")
    
    return _queue_instance
