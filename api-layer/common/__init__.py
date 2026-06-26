"""
L1 API Layer - Common Utilities

Base HTTP client, rate limiting, retry, error handling, unified data models.
"""

from .base_client import BaseClient
from .errors import (
    APIError,
    AuthError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from .rate_limiter import RateLimiter, TokenBucket
from .retry import RetryPolicy, exponential_backoff
from .models import (
    Campaign,
    AdGroup,
    Creative,
    ReportRow,
    Platform,
)

__all__ = [
    "BaseClient",
    "APIError",
    "AuthError",
    "RateLimitError",
    "ServerError",
    "ValidationError",
    "RateLimiter",
    "TokenBucket",
    "RetryPolicy",
    "exponential_backoff",
    "Campaign",
    "AdGroup",
    "Creative",
    "ReportRow",
    "Platform",
]
