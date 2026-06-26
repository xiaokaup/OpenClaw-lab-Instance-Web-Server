"""
OceanEngine (巨量引擎) OAuth2 auth flow.

Two grant types:
1. Authorization code → access_token + refresh_token
2. Refresh token → new access_token (refresh_token valid for 30 days)
"""

import logging
from typing import Optional
from datetime import datetime, timedelta

import httpx

from ..common.errors import AuthError
from .config import TOKEN_URL, REFRESH_URL

logger = logging.getLogger("api-layer.oceanengine.auth")


class OceanEngineAuth:
    """Manages OceanEngine OAuth2 lifecycle.

    Token lifecycle:
    - access_token: expires in 24 hours
    - refresh_token: expires in 30 days, one-time use (each refresh returns a new one)
    """

    TOKEN_ENDPOINT = "https://api.oceanengine.com/open_api/oauth2/access_token/"

    def __init__(
        self,
        app_id: str,
        secret: str,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ):
        self.app_id = app_id
        self.secret = secret
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = expires_at
        self._advertiser_ids: list[str] = []

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return True
        # Buffer: refresh 5 min before actual expiry
        return datetime.now() + timedelta(minutes=5) >= self.expires_at

    async def get_token(self, auth_code: str) -> dict:
        """Exchange authorization code for tokens.

        Call this once when user authorizes your app.
        Returns: {"access_token": "...", "refresh_token": "...", "expires_in": 86400}
        """
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.TOKEN_ENDPOINT,
                json={
                    "app_id": self.app_id,
                    "secret": self.secret,
                    "grant_type": "auth_code",
                    "auth_code": auth_code,
                },
            )
            data = resp.json()
            
            if resp.status_code != 200 or data.get("code") != 0:
                raise AuthError(
                    f"Failed to exchange auth code: {data.get('message', data)}",
                    platform="oceanengine",
                    status_code=resp.status_code,
                    response_body=str(data),
                )
            
            self.access_token = data["data"]["access_token"]
            self.refresh_token = data["data"]["refresh_token"]
            self.expires_at = datetime.now() + timedelta(seconds=data["data"]["expires_in"])
            
            logger.info("OceanEngine tokens obtained, expires at %s", self.expires_at)
            return data["data"]

    async def refresh(self) -> bool:
        """Refresh the access token. Returns True on success.

        OceanEngine's refresh is one-time-use: each refresh returns a NEW refresh_token.
        """
        if not self.refresh_token:
            logger.warning("No refresh token available")
            return False

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                REFRESH_URL,
                json={
                    "app_id": self.app_id,
                    "secret": self.secret,
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                },
            )
            data = resp.json()

            if resp.status_code != 200 or data.get("code") != 0:
                logger.error("Token refresh failed: %s", data.get("message"))
                return False

            self.access_token = data["data"]["access_token"]
            self.refresh_token = data["data"]["refresh_token"]  # NEW refresh token!
            self.expires_at = datetime.now() + timedelta(seconds=data["data"]["expires_in"])
            
            logger.info("OceanEngine tokens refreshed, new expiry: %s", self.expires_at)
            return True

    async def get_advertiser_ids(self, access_token: str) -> list[str]:
        """Get authorized advertiser IDs for this token."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.oceanengine.com/open_api/oauth2/advertiser/get/",
                params={"access_token": access_token},
            )
            data = resp.json()
            if data.get("code") == 0:
                self._advertiser_ids = [
                    str(item["advertiser_id"])
                    for item in data.get("data", {}).get("list", [])
                ]
                return self._advertiser_ids
            return []
