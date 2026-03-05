"""Retry utilities with exponential backoff.

Provides decorators and helper functions for implementing robust
retry logic with configurable backoff strategies.
"""

import functools
import logging
import random
import time
from typing import Callable, TypeVar, ParamSpec

import requests

logger = logging.getLogger(__name__)

P = ParamSpec('P')
T = TypeVar('T')


class RetryError(Exception):
    """Raised when all retry attempts have been exhausted."""

    def __init__(self, message: str, last_exception: Exception | None = None):
        super().__init__(message)
        self.last_exception = last_exception


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_on: tuple[type[Exception], ...] = (requests.RequestException,),
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator that retries a function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay between retries in seconds (default: 1.0)
        max_delay: Maximum delay between retries in seconds (default: 30.0)
        exponential_base: Base for exponential backoff (default: 2.0)
        jitter: Add random jitter to prevent thundering herd (default: True)
        retry_on: Tuple of exception types to retry on (default: requests.RequestException)

    Returns:
        Decorated function that automatically retries on specified exceptions.

    Example:
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        def fetch_data(url: str) -> dict:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retry_on as e:
                    last_exception = e

                    if attempt == max_retries:
                        # Last attempt failed, don't retry
                        break

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)

                    # Add jitter to prevent thundering herd
                    if jitter:
                        delay = delay * (0.5 + random.random())

                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)

            # All retries exhausted
            raise RetryError(
                f"{func.__name__} failed after {max_retries + 1} attempts",
                last_exception
            )

        return wrapper
    return decorator


def is_transient_error(exception: Exception) -> bool:
    """
    Determine if an exception is likely transient and worth retrying.

    Args:
        exception: The exception to check

    Returns:
        True if the error is likely transient, False otherwise
    """
    if isinstance(exception, requests.RequestException):
        # Connection errors, timeouts are transient
        if isinstance(exception, (
            requests.ConnectionError,
            requests.Timeout,
        )):
            return True

        # Check HTTP status codes for retryable errors
        if hasattr(exception, 'response') and exception.response is not None:
            status = exception.response.status_code
            # 429 (rate limit), 500, 502, 503, 504 are transient
            return status in (429, 500, 502, 503, 504)

    return False


# Convenience aliases for common retry configurations
def retry_http(
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Retry decorator optimized for HTTP requests.

    Uses sensible defaults for web scraping:
    - 3 retries with exponential backoff
    - Jitter enabled to prevent rate limit hits
    - Retries on common HTTP errors
    """
    return retry_with_backoff(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=30.0,
        exponential_base=2.0,
        jitter=True,
        retry_on=(requests.RequestException,),
    )


