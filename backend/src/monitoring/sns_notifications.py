"""SNS integration for job completion notifications (LocalStack or AWS)."""

import json
import logging
import os
from typing import Optional, Dict, Any
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

logger = logging.getLogger(__name__)


class SNSNotifier:
    """SNS client for sending notifications (LocalStack or AWS)."""
    
    def __init__(
        self,
        topic_arn: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region_name: str = "us-east-1",
    ):
        """
        Initialize SNS client.
        
        Args:
            topic_arn: SNS topic ARN (optional, can be set per message)
            endpoint_url: Custom endpoint URL (for LocalStack)
            aws_access_key_id: AWS access key
            aws_secret_access_key: AWS secret key
            region_name: AWS region
        """
        self.topic_arn = topic_arn
        self.endpoint_url = endpoint_url
        
        # Get credentials
        self.aws_access_key_id = aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID", "test")
        self.aws_secret_access_key = aws_secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY", "test")
        self.region_name = region_name
        
        # Create SNS client
        config = Config(
            retries={'max_attempts': 3, 'mode': 'standard'}
        )
        
        self.sns_client = boto3.client(
            'sns',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name,
            config=config,
        )
    
    def create_topic(self, topic_name: str) -> Optional[str]:
        """
        Create SNS topic and return ARN.
        
        Args:
            topic_name: Topic name
            
        Returns:
            Topic ARN or None if failed
        """
        try:
            response = self.sns_client.create_topic(Name=topic_name)
            topic_arn = response['TopicArn']
            logger.info(f"✅ Created SNS topic '{topic_name}': {topic_arn}")
            return topic_arn
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == 'InvalidParameter':
                # Topic might already exist, try to get it
                try:
                    topics = self.sns_client.list_topics()['Topics']
                    for topic in topics:
                        if topic['TopicArn'].endswith(f':{topic_name}'):
                            logger.debug(f"Topic '{topic_name}' already exists")
                            return topic['TopicArn']
                except Exception:
                    pass
            logger.error(f"Failed to create SNS topic '{topic_name}': {e}")
            return None
    
    def publish(
        self,
        message: Dict[str, Any],
        subject: Optional[str] = None,
        topic_arn: Optional[str] = None,
    ) -> bool:
        """
        Publish message to SNS topic.
        
        Args:
            message: Message body as dictionary
            subject: Optional message subject
            topic_arn: Topic ARN (uses instance default if not provided)
            
        Returns:
            True if successful, False otherwise
        """
        topic = topic_arn or self.topic_arn
        if not topic:
            logger.error("No topic ARN provided")
            return False
        
        try:
            message_string = json.dumps(message)
            
            self.sns_client.publish(
                TopicArn=topic,
                Message=message_string,
                Subject=subject or "Audiobook Job Notification",
            )
            logger.debug(f"Published notification to {topic}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish notification: {e}")
            return False
    
    def subscribe_email(self, topic_arn: Optional[str] = None, email: str = "") -> bool:
        """
        Subscribe email address to topic.
        
        Args:
            topic_arn: Topic ARN (uses instance default if not provided)
            email: Email address
            
        Returns:
            True if successful, False otherwise
        """
        topic = topic_arn or self.topic_arn
        if not topic:
            logger.error("No topic ARN provided")
            return False
        
        try:
            response = self.sns_client.subscribe(
                TopicArn=topic,
                Protocol='email',
                Endpoint=email,
            )
            logger.info(f"✅ Subscribed {email} to {topic}: {response['SubscriptionArn']}")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe email: {e}")
            return False


def get_sns_notifier() -> Optional[SNSNotifier]:
    """
    Get or create SNS notifier instance.
    
    Returns:
        SNSNotifier instance or None if not configured
    """
    from src.utils.config import get_settings
    settings = get_settings()
    
    if not settings.sns_topic_arn:
        return None
    
    return SNSNotifier(
        topic_arn=settings.sns_topic_arn,
        endpoint_url=settings.sns_endpoint_url,
    )
