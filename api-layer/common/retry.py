"""
Retry policy with exponential backoff and jitter.

Used by BaseClient for transient failures (429, 5xx, network errors).
"""

import asyncio
import random
from typing import Callable, Awaitable, TypeVar

T = TypeVar("T")


def exponential_backoff(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
) -> float:
    """Calculate delay for exponential backoff.

    delay = min(base_delay * 2^attempt, max_delay)
    With jitter: delay *= random(0.5, 1.5)
    """
    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
    if jitter:
        delay *= random.uniform(0.5, 1.5)
    return delay


class RetryPolicy:
    """Configurable retry policy for API calls."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        retryable_statuses: set[int] | None = None,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.retryable_statuses = retryable_statuses or {429, 500, 502, 503, 504}

    def is_retryable(self, status_code: int) -> bool:
        return status_code in self.retryable_statuses

    async def execute(
        self,
        fn: Callable[..., Awaitable[T]],
        *args,
        **kwargs,
    ) -> T:
        """Execute fn with retry logic. Raises last error if all retries exhausted."""
        from .errors import APIError
        
        last_error = None
        
        for attempt in range(1, self.max_retries + 2):  # 1 initial + max_retries retries
            try:
                return await fn(*args, **kwargs)
            except APIError as e:
                if not e.retryable and not self.is_retryable(e.status_code or 0):
                    raise
                last_error = e
                if attempt > self.max_retries:
                    break
            except Exception as e:
                # Network/connection errors are always retryable
                last_error = e
                if attempt > self.max_retries:
                    break
            
            delay = exponential_backoff(attempt, self.base_delay, self.max_delay)
            await asyncio.sleep(delay)
        
        raise last_error  # type: ignore


# Sensible defaults per platform
DEFAULT_RETRY = RetryPolicy(max_retries=3)
AGGRESSIVE_RETRY = RetryPolicy(max_retries=5, base_delay=0.5)  # for report polling
