"""
Token-bucket rate limiter for platform API call throttling.

Usage:
    limiter = RateLimiter()
    oceanengine_limiter = limiter.get("oceanengine", qps=10)
    
    async with oceanengine_limiter:
        await client.request(...)
"""

import asyncio
import time
from dataclasses import dataclass


@dataclass
class TokenBucket:
    """Token bucket algorithm for smooth rate limiting."""
    rate: float        # tokens per second (sustained QPS)
    burst: int         # max burst size
    tokens: float      # current tokens
    last_refill: float # timestamp of last refill

    async def acquire(self) -> float:
        """Acquire one token. Returns wait time (0 if available immediately)."""
        now = time.monotonic()
        
        # Refill tokens based on elapsed time
        elapsed = now - self.last_refill
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        self.last_refill = now
        
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return 0.0
        
        # Calculate wait time for next token
        wait = (1.0 - self.tokens) / self.rate
        self.tokens = 0.0
        return wait


class RateLimiter:
    """Manages per-platform rate limiters."""

    def __init__(self):
        self._buckets: dict[str, TokenBucket] = {}

    def get(self, platform: str, qps: float = 10, burst: int = 20) -> "RateLimitContext":
        """Get or create a rate limit context for a platform.
        
        Args:
            platform: Platform identifier (e.g., 'oceanengine', 'wechat_ads')
            qps: Sustained queries per second
            burst: Maximum burst size
        """
        if platform not in self._buckets:
            self._buckets[platform] = TokenBucket(
                rate=qps,
                burst=burst or max(1, int(qps * 2)),
                tokens=float(burst or int(qps * 2)),
                last_refill=time.monotonic(),
            )
        return RateLimitContext(self._buckets[platform])


class RateLimitContext:
    """Async context manager for rate-limited operations."""

    def __init__(self, bucket: TokenBucket):
        self._bucket = bucket
        self._wait = 0.0

    async def __aenter__(self):
        self._wait = await self._bucket.acquire()
        if self._wait > 0:
            await asyncio.sleep(self._wait)

    async def __aexit__(self, *args):
        pass
