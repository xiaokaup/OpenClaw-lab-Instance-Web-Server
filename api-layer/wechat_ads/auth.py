"""
WeChat Ads OAuth2 auth flow.

WeChat uses:
- Client credentials (client_id + client_secret) to get access_token
- Access token is valid for 2 hours (7200s)
- Refresh with refresh_token before expiry
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

from ..common.errors import AuthError

logger = logging.getLogger("api-layer.wechat_ads.auth")


class WeChatAdsAuth:
    """Manages WeChat Ads OAuth2 tokens."""

    TOKEN_URL = "https://api.weixin.qq.com/oauth2/token"
    REFRESH_URL = "https://api.weixin.qq.com/oauth2/refresh_token"

    def __init__(
        self,
        client_id: str,       # 广告主 app_id
        client_secret: str,   # 广告主 app_secret
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        account_id: Optional[str] = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = expires_at
        self.account_id = account_id  # WeChat ad account ID

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return True
        # Buffer: refresh 10 min before actual expiry
        return datetime.now() + timedelta(minutes=10) >= self.expires_at

    async def get_token(self) -> dict:
        """Get access token using client credentials flow.

        Returns: {
            "access_token": "...",
            "refresh_token": "...",
            "expires_in": 7200,
            "authorizer_info": {...}
        }
        """
        # If we have a refresh token, use it
        if self.refresh_token:
            return await self.refresh()

        # Fresh authorization
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.TOKEN_URL,
                params={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                },
            )
            data = resp.json()

            if resp.status_code != 200 or data.get("errcode", -1) != 0:
                raise AuthError(
                    f"WeChat token failed: {data.get('errmsg', data)}",
                    platform="wechat_ads",
                    status_code=resp.status_code,
                    response_body=str(data),
                )

            self.access_token = data["access_token"]
            self.refresh_token = data.get("refresh_token", "")
            self.expires_at = datetime.now() + timedelta(seconds=data.get("expires_in", 7200))

            if data.get("authorizer_info"):
                self.account_id = str(data["authorizer_info"].get("account_id", ""))

            logger.info("WeChat Ads token obtained, account: %s, expires: %s",
                       self.account_id, self.expires_at)
            return data

    async def refresh(self) -> bool:
        """Refresh access token. Returns True on success."""
        if not self.refresh_token:
            logger.warning("No refresh token available for WeChat Ads")
            return False

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.REFRESH_URL,
                params={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                },
            )
            data = resp.json()

            if resp.status_code != 200 or data.get("errcode", -1) != 0:
                logger.error("WeChat token refresh failed: %s", data.get("errmsg"))
                return False

            self.access_token = data["access_token"]
            self.refresh_token = data.get("refresh_token", self.refresh_token)
            self.expires_at = datetime.now() + timedelta(seconds=data.get("expires_in", 7200))

            logger.info("WeChat Ads token refreshed, new expiry: %s", self.expires_at)
            return True
