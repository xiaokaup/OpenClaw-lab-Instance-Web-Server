"""
Base async HTTP client for all platform APIs.

Provides:
- Async HTTP via httpx
- Automatic auth header injection
- Token refresh on 401
- Rate limiting per platform
- Retry with backoff
- Structured logging
- Error normalization
"""

import json
import logging
from typing import Any, Optional

import httpx

from .errors import (
    APIError,
    AuthError,
    BudgetError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from .rate_limiter import RateLimiter
from .retry import DEFAULT_RETRY, RetryPolicy

logger = logging.getLogger("api-layer")


class BaseClient:
    """Base client for all advertising platform APIs."""

    # Platform-specific base URL, set by subclasses
    BASE_URL: str = ""
    PLATFORM: str = "unknown"

    def __init__(
        self,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        qps: float = 10,
        retry_policy: Optional[RetryPolicy] = None,
        timeout: float = 30.0,
    ):
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._rate_limiter = RateLimiter().get(self.PLATFORM, qps=qps)
        self._retry = retry_policy or DEFAULT_RETRY
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def access_token(self) -> Optional[str]:
        return self._access_token

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                timeout=httpx.Timeout(self._timeout),
                headers=self._default_headers(),
            )
        return self._client

    def _default_headers(self) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._access_token:
            headers["Access-Token"] = self._access_token
        return headers

    # ── Auth hooks (overridden by platform subclasses) ──────────

    def _is_token_expired_error(self, response: httpx.Response, body: dict) -> bool:
        """Check if the error indicates token expiry. Override per platform."""
        return response.status_code == 401

    async def _refresh_access_token(self) -> bool:
        """Attempt token refresh. Return True on success. Override per platform."""
        return False

    # ── Error normalization ──────────────────────────────────────

    def _normalize_error(
        self,
        response: httpx.Response,
        body: dict,
    ) -> APIError:
        """Map a bad response to a unified error type."""
        status = response.status_code
        message = body.get("message", "") or body.get("error", "") or str(body)

        if status == 401 or status == 403:
            return AuthError(message, platform=self.PLATFORM, status_code=status,
                            response_body=json.dumps(body))
        if status == 429:
            retry_after = response.headers.get("Retry-After")
            return RateLimitError(message, platform=self.PLATFORM,
                                 status_code=status,
                                 retry_after=int(retry_after) if retry_after else None)
        if status >= 500:
            return ServerError(message, platform=self.PLATFORM, status_code=status,
                             response_body=json.dumps(body))
        if status == 400 or status == 422:
            return ValidationError(message, platform=self.PLATFORM, status_code=status,
                                 response_body=json.dumps(body))
        return APIError(message, platform=self.PLATFORM, status_code=status,
                       response_body=json.dumps(body))

    # ── Core HTTP methods ────────────────────────────────────────

    async def request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        json_data: Optional[dict] = None,
    ) -> dict:
        """Make an API request with full middleware stack (auth, rate limit, retry)."""
        return await self._retry.execute(
            self._do_request, method, path, params, json_data
        )

    async def _do_request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        json_data: Optional[dict] = None,
    ) -> dict:
        """Internal: single request attempt with rate limiting and auth refresh."""
        async with self._rate_limiter:
            client = await self._get_client()

            # Update auth header (token may have been refreshed)
            if self._access_token:
                client.headers["Access-Token"] = self._access_token

            logger.debug("[%s] %s %s", self.PLATFORM, method, path)

            response = await client.request(
                method=method,
                url=path,
                params=params,
                json=json_data,
            )

            # Try to parse JSON body
            try:
                body = response.json()
            except json.JSONDecodeError:
                body = {"error": response.text}

            if response.is_success:
                return body

            # Token expired? Try refresh and retry once
            if self._is_token_expired_error(response, body):
                if await self._refresh_access_token():
                    client.headers["Access-Token"] = self._access_token
                    response = await client.request(
                        method=method, url=path, params=params, json=json_data
                    )
                    if response.is_success:
                        return response.json()

            # Normalize and raise
            raise self._normalize_error(response, body)

    async def get(self, path: str, params: Optional[dict] = None) -> dict:
        return await self.request("GET", path, params=params)

    async def post(self, path: str, json_data: Optional[dict] = None) -> dict:
        return await self.request("POST", path, json_data=json_data)

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
