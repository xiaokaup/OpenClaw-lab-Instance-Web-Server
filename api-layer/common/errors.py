"""
Unified exceptions for the L1 API layer.

All platform-specific errors should be mapped to these types
so upper-layer code (投投, 控控) doesn't need platform-specific logic.
"""

from typing import Optional


class APIError(Exception):
    """Base error for all API layer issues."""

    def __init__(
        self,
        message: str,
        platform: Optional[str] = None,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.platform = platform
        self.status_code = status_code
        self.response_body = response_body
        self.retryable = retryable


class AuthError(APIError):
    """Authentication/authorization failure (401/403).

    Triggers token refresh flow in BaseClient.
    """
    def __init__(self, message: str, **kwargs):
        super().__init__(message, **kwargs)
        self.retryable = False  # auth errors need token refresh, not retry


class RateLimitError(APIError):
    """Rate limit exceeded (429).

    Always retryable with backoff.
    """
    def __init__(
        self,
        message: str,
        retry_after: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(message, retryable=True, **kwargs)
        self.retry_after = retry_after


class ServerError(APIError):
    """Server-side error (5xx).

    Retryable by default.
    """
    def __init__(self, message: str, **kwargs):
        super().__init__(message, retryable=True, **kwargs)


class ValidationError(APIError):
    """Request validation error (400/422).

    NOT retryable — the request itself is wrong.
    """
    def __init__(self, message: str, **kwargs):
        super().__init__(message, retryable=False, **kwargs)


class BudgetError(APIError):
    """Budget-related errors (insufficient balance, budget exceeded).

    Important for 控控's meltdown detection.
    """
    def __init__(self, message: str, **kwargs):
        super().__init__(message, retryable=False, **kwargs)
