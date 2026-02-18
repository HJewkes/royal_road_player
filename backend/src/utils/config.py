"""Configuration management."""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load environment variables
load_dotenv()


def get_project_root() -> Path:
    """
    Get the project root directory.
    
    This resolves to the directory containing backend/ and frontend/ directories,
    regardless of where the code is executed from.
    """
    # This file is at backend/src/utils/config.py
    # Project root is 3 levels up: backend/src/utils -> backend/src -> backend -> project_root
    return Path(__file__).parent.parent.parent.parent


class Settings(BaseSettings):
    """Application settings."""

    # Ollama Configuration
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    # TTS Configuration (XTTS v2)
    tts_model: str = "tts_models/multilingual/multi-dataset/xtts_v2"  # XTTS v2 model (legacy, use tts_fine_tuned_model instead)
    tts_fine_tuned_model: Optional[str] = None  # Fine-tuned model name from registry (e.g., 'david_attenborough', 'morgan_freeman')
    tts_speaker: Optional[str] = None  # Speaker reference WAV file path for voice cloning
    tts_speed: float = 1.0  # Speech speed multiplier (0.5-2.0)
    tts_gpu: bool = False  # Use GPU/MPS if available (set to True to enable)
    tts_num_threads: Optional[int] = None  # Number of CPU threads (None = auto, set to match CPU cores)
    
    # Audio Output Configuration
    audio_output_format: str = "m4b"  # Output format: wav, m4b, m4a, mp3, flac, ogg
    audio_bitrate: str = "128k"  # Audio bitrate for compressed formats (128k, 192k, 256k)
    audio_generate_chapters: bool = True  # Generate chapter markers in output files

    # Web Application
    web_host: str = "127.0.0.1"
    web_port: int = 8000
    debug: bool = False

    # Database
    database_path: Optional[str] = None  # SQLite database path
    
    # Data Paths - will be computed relative to project root in __init__
    # These are placeholders for Pydantic validation
    data_dir: Optional[Path] = None
    books_dir: Optional[Path] = None
    audio_dir: Optional[Path] = None
    log_dir: Optional[Path] = None

    # Scraper Configuration
    scraper_delay_seconds: int = 2
    scraper_user_agent: str = "Mozilla/5.0 (compatible; AudiobookBot/1.0)"
    scraper_retry_attempts: int = 3

    # Logging
    log_level: str = "INFO"
    
    # Job Queue
    enable_background_processor: bool = True  # Enable/disable background job processing
    
    # S3 Storage Configuration
    s3_bucket_name: str = "audiobook-data"  # S3 bucket name
    s3_endpoint_url: Optional[str] = None  # Custom endpoint (e.g., http://localstack:4566 for LocalStack)
    s3_access_key_id: Optional[str] = None  # AWS access key (uses AWS_ACCESS_KEY_ID env var if not set)
    s3_secret_access_key: Optional[str] = None  # AWS secret key (uses AWS_SECRET_ACCESS_KEY env var if not set)
    s3_region_name: str = "us-east-1"  # AWS region
    s3_use_storage: bool = True  # Enable S3 storage (set to False to use local filesystem)
    
    # SQS Queue Configuration
    sqs_queue_name: str = "audiobook-jobs"  # SQS queue name
    sqs_endpoint_url: Optional[str] = None  # Custom endpoint (e.g., http://localstack:4566 for LocalStack)
    sqs_access_key_id: Optional[str] = None  # AWS access key (uses AWS_ACCESS_KEY_ID env var if not set)
    sqs_secret_access_key: Optional[str] = None  # AWS secret key (uses AWS_SECRET_ACCESS_KEY env var if not set)
    sqs_region_name: str = "us-east-1"  # AWS region
    sqs_use_queue: bool = False  # Enable SQS queue (set to True to use SQS instead of database queue)
    
    # CloudWatch Logs Configuration
    cloudwatch_log_group: Optional[str] = None  # CloudWatch log group name (None = disabled)
    cloudwatch_log_stream: Optional[str] = None  # CloudWatch log stream name (None = auto)
    cloudwatch_endpoint_url: Optional[str] = None  # Custom endpoint (e.g., http://localstack:4566 for LocalStack)
    
    # SNS Notifications Configuration
    sns_topic_arn: Optional[str] = None  # SNS topic ARN for job completion notifications
    sns_endpoint_url: Optional[str] = None  # Custom endpoint (e.g., http://localstack:4566 for LocalStack)
    
    # Secrets Manager Configuration
    secrets_manager_endpoint_url: Optional[str] = None  # Custom endpoint (e.g., http://localstack:4566 for LocalStack)
    use_secrets_manager: bool = False  # Enable Secrets Manager for credentials (set to True in production)

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def __init__(self, **kwargs):
        """Initialize settings and create directories."""
        super().__init__(**kwargs)
        # Compute paths relative to project root (not current working directory)
        project_root = get_project_root()
        self.data_dir = project_root / "data"
        self.books_dir = project_root / "data" / "books"
        self.audio_dir = project_root / "data" / "books"
        self.log_dir = project_root / "logs"
        
        # Set database path if not provided
        if self.database_path is None:
            databases_dir = project_root / "data" / "databases"
            databases_dir.mkdir(parents=True, exist_ok=True)
            self.database_path = str(databases_dir / "audiobook.db")
        
        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.books_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings

