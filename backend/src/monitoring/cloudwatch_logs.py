"""CloudWatch Logs integration for centralized logging (LocalStack or AWS)."""

import json
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

logger = logging.getLogger(__name__)


class CloudWatchLogsHandler(logging.Handler):
    """Logging handler that sends logs to CloudWatch Logs."""
    
    def __init__(
        self,
        log_group_name: str,
        log_stream_name: str,
        endpoint_url: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region_name: str = "us-east-1",
    ):
        """
        Initialize CloudWatch Logs handler.
        
        Args:
            log_group_name: CloudWatch log group name
            log_stream_name: CloudWatch log stream name
            endpoint_url: Custom endpoint URL (for LocalStack)
            aws_access_key_id: AWS access key
            aws_secret_access_key: AWS secret key
            region_name: AWS region
        """
        super().__init__()
        self.log_group_name = log_group_name
        self.log_stream_name = log_stream_name
        
        # Get credentials
        self.aws_access_key_id = aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID", "test")
        self.aws_secret_access_key = aws_secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY", "test")
        self.region_name = region_name
        
        # Create CloudWatch Logs client
        config = Config(
            retries={'max_attempts': 3, 'mode': 'standard'}
        )
        
        self.logs_client = boto3.client(
            'logs',
            endpoint_url=endpoint_url,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name,
            config=config,
        )
        
        # Ensure log group and stream exist
        self._ensure_log_group()
        self._ensure_log_stream()
        
        # Buffer for batch sending
        self._log_buffer: List[Dict[str, Any]] = []
        self._buffer_size = 10  # Send in batches of 10
    
    def _ensure_log_group(self) -> None:
        """Ensure log group exists, create if it doesn't."""
        try:
            self.logs_client.describe_log_groups(logGroupNamePrefix=self.log_group_name)
            # Check if exact match exists
            groups = self.logs_client.describe_log_groups(logGroupNamePrefix=self.log_group_name)['logGroups']
            if any(g['logGroupName'] == self.log_group_name for g in groups):
                logger.debug(f"Log group '{self.log_group_name}' exists")
                return
        except ClientError:
            pass
        
        # Create log group
        try:
            self.logs_client.create_log_group(logGroupName=self.log_group_name)
            logger.info(f"✅ Created log group '{self.log_group_name}'")
        except ClientError as e:
            if e.response.get('Error', {}).get('Code') != 'ResourceAlreadyExistsException':
                logger.error(f"Failed to create log group '{self.log_group_name}': {e}")
    
    def _ensure_log_stream(self) -> None:
        """Ensure log stream exists, create if it doesn't."""
        try:
            self.logs_client.describe_log_streams(
                logGroupName=self.log_group_name,
                logStreamNamePrefix=self.log_stream_name
            )
            logger.debug(f"Log stream '{self.log_stream_name}' exists")
        except ClientError:
            pass
        
        # Create log stream
        try:
            self.logs_client.create_log_stream(
                logGroupName=self.log_group_name,
                logStreamName=self.log_stream_name
            )
            logger.info(f"✅ Created log stream '{self.log_stream_name}'")
        except ClientError as e:
            if e.response.get('Error', {}).get('Code') != 'ResourceAlreadyExistsException':
                logger.error(f"Failed to create log stream '{self.log_stream_name}': {e}")
    
    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to CloudWatch Logs."""
        try:
            # Format log message
            message = self.format(record)
            
            # Create log event
            log_event = {
                'timestamp': int(record.created * 1000),  # CloudWatch uses milliseconds
                'message': message,
            }
            
            # Add to buffer
            self._log_buffer.append(log_event)
            
            # Send batch if buffer is full
            if len(self._log_buffer) >= self._buffer_size:
                self._flush_buffer()
        except Exception as e:
            logger.error(f"Failed to emit log to CloudWatch: {e}")
    
    def _flush_buffer(self) -> None:
        """Flush log buffer to CloudWatch Logs."""
        if not self._log_buffer:
            return
        
        try:
            self.logs_client.put_log_events(
                logGroupName=self.log_group_name,
                logStreamName=self.log_stream_name,
                logEvents=self._log_buffer,
            )
            self._log_buffer.clear()
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == 'InvalidSequenceTokenException':
                # Get next sequence token and retry
                try:
                    streams = self.logs_client.describe_log_streams(
                        logGroupName=self.log_group_name,
                        logStreamNamePrefix=self.log_stream_name
                    )['logStreams']
                    if streams:
                        sequence_token = streams[0].get('uploadSequenceToken')
                        if sequence_token:
                            self.logs_client.put_log_events(
                                logGroupName=self.log_group_name,
                                logStreamName=self.log_stream_name,
                                logEvents=self._log_buffer,
                                sequenceToken=sequence_token,
                            )
                            self._log_buffer.clear()
                except Exception as retry_error:
                    logger.error(f"Failed to retry log upload: {retry_error}")
            else:
                logger.error(f"Failed to flush logs to CloudWatch: {e}")
    
    def flush(self) -> None:
        """Flush any remaining logs in buffer."""
        self._flush_buffer()
        super().flush()


def setup_cloudwatch_logging(
    log_group_name: str,
    log_stream_name: Optional[str] = None,
    endpoint_url: Optional[str] = None,
    level: int = logging.INFO,
) -> Optional[CloudWatchLogsHandler]:
    """
    Set up CloudWatch Logs handler for application logging.
    
    Args:
        log_group_name: CloudWatch log group name
        log_stream_name: Log stream name (defaults to hostname or 'default')
        endpoint_url: Custom endpoint URL (for LocalStack)
        level: Logging level
        
    Returns:
        CloudWatchLogsHandler instance or None if setup fails
    """
    import socket
    
    if log_stream_name is None:
        log_stream_name = socket.gethostname() or 'default'
    
    try:
        handler = CloudWatchLogsHandler(
            log_group_name=log_group_name,
            log_stream_name=log_stream_name,
            endpoint_url=endpoint_url,
        )
        handler.setLevel(level)
        
        # Add formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        
        # Add to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        
        logger.info(f"✅ CloudWatch Logs handler configured: {log_group_name}/{log_stream_name}")
        return handler
    except Exception as e:
        logger.error(f"Failed to setup CloudWatch Logs: {e}")
        return None
