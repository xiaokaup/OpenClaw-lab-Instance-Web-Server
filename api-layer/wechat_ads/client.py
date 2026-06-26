"""
WeChat Ads (微信广告) full API client.

Handles: 朋友圈 + 公众号 + 视频号 + 小程序 全广告位投放.

Usage:
    auth = WeChatAdsAuth(client_id="...", client_secret="...")
    await auth.get_token()
    
    client = WeChatAdsClient(auth)
    
    # Create ad group targeting WeChat Moments
    adgroup = await client.create_adgroup(
        name="人格测试-朋友圈-R1",
        site_set=["SITE_SET_MOMENTS"],
        daily_budget=50000,   # 500 RMB in fen
    )
"""

import logging
from datetime import date, datetime
from typing import Any, Optional

import httpx

from ..common.base_client import BaseClient
from ..common.errors import APIError, ValidationError
from ..common.models import (
    Campaign,
    CampaignStatus,
    Creative,
    Platform,
    ReportRow,
)
from .auth import WeChatAdsAuth
from . import config

logger = logging.getLogger("api-layer.wechat_ads")


class WeChatAdsClient(BaseClient):
    """Full WeChat Ads Marketing API client."""

    BASE_URL = "https://api.weixin.qq.com/marketing"
    PLATFORM = "wechat_ads"

    def __init__(
        self,
        auth: WeChatAdsAuth,
        qps: float = 10,
        timeout: float = 30.0,
    ):
        super().__init__(
            access_token=auth.access_token,
            refresh_token=auth.refresh_token,
            qps=qps,
            timeout=timeout,
        )
        self._auth = auth
        self._account_id = auth.account_id

    # ── Auth hooks ────────────────────────────────────────────────

    def _is_token_expired_error(self, response: httpx.Response, body: dict) -> bool:
        errcode = body.get("errcode", 0)
        return errcode in (40001, 40014, 42001)  # invalid/expired token codes

    async def _refresh_access_token(self) -> bool:
        if await self._auth.refresh():
            self._access_token = self._auth.access_token
            self._refresh_token = self._auth.refresh_token
            return True
        return False

    # ── Helpers ───────────────────────────────────────────────────

    def _account_params(self, extra: Optional[dict] = None) -> dict:
        """Add required account_id to query params."""
        params: dict = {"access_token": self._access_token or ""}
        if self._account_id:
            params["account_id"] = self._account_id
        if extra:
            params.update(extra)
        return params

    def _date_str(self, d: date | str) -> str:
        if isinstance(d, date):
            return d.strftime("%Y-%m-%d")
        return d

    def _check_response(self, body: dict, context: str = "request") -> None:
        """WeChat uses 'errcode' (not 'code') for errors."""
        errcode = body.get("errcode", 0)
        if errcode != 0:
            raise APIError(
                f"[{context}] WeChat Ads error {errcode}: {body.get('errmsg', 'unknown')}",
                platform=self.PLATFORM,
                response_body=str(body),
            )

    def _status_map(self, status: str) -> CampaignStatus:
        mapping = {
            "ADGROUP_STATUS_NORMAL": CampaignStatus.ACTIVE,
            "ADGROUP_STATUS_SUSPEND": CampaignStatus.PAUSED,
            "ADGROUP_STATUS_DELETE": CampaignStatus.DELETED,
            "AD_STATUS_NORMAL": CampaignStatus.ACTIVE,
            "AD_STATUS_SUSPEND": CampaignStatus.PAUSED,
        }
        return mapping.get(status, CampaignStatus.PENDING)

    # ══════════════════════════════════════════════════════════════
    # Adgroup (广告组)
    # ══════════════════════════════════════════════════════════════

    async def create_adgroup(
        self,
        name: str,
        site_set: list[str],         # e.g., ["SITE_SET_MOMENTS", "SITE_SET_WECHAT"]
        daily_budget: float,         # in 分 (e.g., 50000 = 500 RMB/day)
        # Targeting (all optional, default = broad)
        gender: Optional[list[str]] = None,    # ["MALE"] / ["FEMALE"] / ["MALE", "FEMALE"]
        age: Optional[list[str]] = None,       # ["18~24", "25~34", ...]
        city_ids: Optional[list[int]] = None,  # WeChat city codes
        interest_tags: Optional[list[int]] = None, # WeChat interest tag IDs
        # Bidding
        bid_type: str = "BID_TYPE_CPC",
        bid_amount: float = 1000,    # in 分 (10 RMB CPC)
        # Schedule
        begin_date: Optional[date] = None,
        end_date: Optional[date] = None,
        time_series: Optional[str] = None,  # "111111111111111111111111..." 24*7 bits
    ) -> Campaign:
        """Create an adgroup (广告组)."""
        targeting: dict = {}
        if gender:
            targeting["gender"] = gender
        if age:
            targeting["age"] = age
        if city_ids:
            targeting["city"] = city_ids
        if interest_tags:
            targeting["interest"] = interest_tags

        json_data: dict[str, Any] = {
            "adgroup_name": name,
            "site_set": site_set,
            "daily_budget": daily_budget,
            "bid_type": bid_type,
            "bid_amount": bid_amount,
        }
        if targeting:
            json_data["targeting"] = targeting
        if begin_date:
            json_data["begin_date"] = begin_date.strftime("%Y-%m-%d")
            # WeChat requires end_date if begin_date is set
            json_data["end_date"] = (end_date or begin_date.replace(year=begin_date.year + 1)).strftime("%Y-%m-%d")
        if time_series:
            json_data["time_series"] = time_series

        body = await self.post(
            config.ADGROUP_ADD,
            json_data=json_data,
        )
        self._check_response(body, "create_adgroup")

        data = body["data"]
        return Campaign(
            external_id=str(data["adgroup_id"]),
            platform=Platform.WECHAT_ADS,
            name=name,
            status=CampaignStatus.PENDING,
            budget=daily_budget,
            budget_type="daily",
            daily_budget=daily_budget,
            raw_data=data,
        )

    async def get_adgroups(
        self,
        adgroup_ids: Optional[list[str]] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> list[Campaign]:
        """List adgroups."""
        params = self._account_params({
            "page": page,
            "page_size": page_size,
        })
        if adgroup_ids:
            params["filtering"] = [{
                "field": "adgroup_id",
                "operator": "IN",
                "values": adgroup_ids,
            }]

        body = await self.get(config.ADGROUP_GET, params=params)
        self._check_response(body, "get_adgroups")

        return [
            Campaign(
                external_id=str(a["adgroup_id"]),
                platform=Platform.WECHAT_ADS,
                name=a["adgroup_name"],
                status=self._status_map(a.get("system_status", "")),
                budget=a.get("daily_budget", 0),
                budget_type="daily",
                daily_budget=a.get("daily_budget", 0),
                start_date=datetime.strptime(a["begin_date"], "%Y-%m-%d") if a.get("begin_date") else None,
                end_date=datetime.strptime(a["end_date"], "%Y-%m-%d") if a.get("end_date") else None,
                raw_data=a,
            )
            for a in body.get("data", {}).get("list", [])
        ]

    # ══════════════════════════════════════════════════════════════
    # Ad (广告)
    # ══════════════════════════════════════════════════════════════

    async def create_ad(
        self,
        adgroup_id: str,
        name: str,
        creative_id: str,
    ) -> dict:
        """Create an ad (广告) linking an adgroup to a creative."""
        body = await self.post(
            config.AD_ADD,
            json_data={
                "adgroup_id": int(adgroup_id),
                "ad_name": name,
                "adcreative_id": int(creative_id),
            },
        )
        self._check_response(body, "create_ad")
        return body["data"]

    # ══════════════════════════════════════════════════════════════
    # Creative (广告创意)
    # ══════════════════════════════════════════════════════════════

    async def create_creative(
        self,
        name: str,
        site_set: str,              # e.g., "SITE_SET_MOMENTS"
        # WeChat Moments creative spec
        title: Optional[str] = None,
        description: Optional[str] = None,
        image_id: Optional[str] = None,
        video_id: Optional[str] = None,
        landing_page_url: Optional[str] = None,
        # Call to action
        button_text: Optional[str] = None,
    ) -> Creative:
        """Create a creative for WeChat ads.

        WeChat creatives have strict spec requirements per placement site.
        """
        creative_elements: dict = {}
        if title:
            creative_elements["title"] = title
        if description:
            creative_elements["description"] = description
        if image_id:
            creative_elements["image"] = image_id
        if video_id:
            creative_elements["video"] = video_id
        if button_text:
            creative_elements["button_text"] = button_text

        json_data: dict[str, Any] = {
            "adcreative_name": name,
            "site_set": [site_set],
            "creative_elements": creative_elements,
        }
        if landing_page_url:
            json_data["page_spec"] = {
                "page_url": landing_page_url,
            }

        body = await self.post(
            config.CREATIVE_ADD,
            json_data=json_data,
        )
        self._check_response(body, "create_creative")

        data = body["data"]
        return Creative(
            external_id=str(data["adcreative_id"]),
            platform=Platform.WECHAT_ADS,
            adgroup_id="",  # linked later in create_ad
            title=title or "",
            description=description or "",
            image_urls=[image_id] if image_id else [],
            video_url=video_id,
            landing_page_url=landing_page_url or "",
            raw_data=data,
        )

    # ══════════════════════════════════════════════════════════════
    # Reports (数据报表)
    # ══════════════════════════════════════════════════════════════

    async def get_daily_report(
        self,
        start_date: date | str,
        end_date: date | str,
        adgroup_id: Optional[str] = None,
        level: str = "ADGROUP",            # "ADGROUP" or "AD" or "CREATIVE"
        page: int = 1,
        page_size: int = 100,
    ) -> list[ReportRow]:
        """Pull daily performance report.

        Primary data source for 控控's budget monitoring.
        """
        params = self._account_params({
            "date_range": {
                "start_date": self._date_str(start_date),
                "end_date": self._date_str(end_date),
            },
            "level": level,
            "page": page,
            "page_size": min(page_size, 100),
        })
        if adgroup_id:
            params["filtering"] = [{
                "field": "adgroup_id",
                "operator": "EQUALS",
                "values": [adgroup_id],
            }]

        body = await self.get(config.DAILY_REPORT, params=params)
        self._check_response(body, "get_daily_report")

        rows = []
        for r in body.get("data", {}).get("list", []):
            report_date = r.get("date", "")
            impressions = r.get("view_count", 0) or r.get("impression", 0)
            clicks = r.get("valid_click_count", 0) or r.get("click", 0)
            cost_yuan = r.get("cost", 0) / 100  # WeChat gives fen, normalize

            rows.append(ReportRow(
                platform=Platform.WECHAT_ADS,
                date=report_date,
                campaign_id=str(r.get("campaign_id", "")),
                adgroup_id=str(r.get("adgroup_id", "")),
                creative_id=str(r.get("adcreative_id", "")),
                cost=cost_yuan * 100 if cost_yuan > 0 else r.get("cost", 0),  # store as fen
                impressions=impressions,
                clicks=clicks,
                ctr=clicks / max(impressions, 1) * 100,
                cpm=(r.get("cost", 0) / max(impressions, 1) * 1000) if impressions > 0 else 0,
                cpc=(r.get("cost", 0) / max(clicks, 1)) if clicks > 0 else 0,
                conversions=r.get("conversions_count", 0),
                conversion_cost=r.get("conversions_cost", 0),
                conversion_rate=r.get("conversions_rate", 0),
                raw_data=r,
            ))

        return rows

    async def get_hourly_report(
        self,
        date_str: date | str,
        level: str = "ADGROUP",
        page: int = 1,
        page_size: int = 100,
    ) -> list[ReportRow]:
        """Pull hourly report for near-real-time monitoring.

        控控 uses this for high-frequency CPA meltdown detection.
        """
        params = self._account_params({
            "date": self._date_str(date_str),
            "level": level,
            "page": page,
            "page_size": min(page_size, 100),
        })

        body = await self.get(config.HOURLY_REPORT, params=params)
        self._check_response(body, "get_hourly_report")

        rows = []
        for r in body.get("data", {}).get("list", []):
            rows.append(ReportRow(
                platform=Platform.WECHAT_ADS,
                date=f"{date_str} T{r.get('hour', 0):02d}:00",
                campaign_id=str(r.get("campaign_id", "")),
                cost=r.get("cost", 0),
                impressions=r.get("impression", 0),
                clicks=r.get("click", 0),
                conversions=r.get("conversions_count", 0),
                conversion_cost=r.get("conversions_cost", 0),
                raw_data=r,
            ))

        return rows

    # ══════════════════════════════════════════════════════════════
    # Audiences (人群管理)
    # ══════════════════════════════════════════════════════════════

    async def create_audience(
        self,
        name: str,
        audience_type: str = "CUSTOMER_FILE",  # or "LOOKALIKE"
        description: str = "",
    ) -> str:
        """Create a custom audience. Returns audience_id."""
        body = await self.post(
            config.AUDIENCE_ADD,
            json_data={
                "name": name,
                "type": audience_type,
                "description": description,
            },
        )
        self._check_response(body, "create_audience")
        return str(body["data"]["audience_id"])

    async def upload_audience_users(
        self,
        audience_id: str,
        user_id_type: str,     # "HASH_MOBILE_PHONE", "HASH_IMEI", "WECHAT_OPENID", etc.
        user_ids: list[str],
    ) -> dict:
        """Upload user IDs to a custom audience."""
        body = await self.post(
            config.AUDIENCE_FILE_ADD,
            json_data={
                "audience_id": int(audience_id),
                "user_id_type": user_id_type,
                "user_id_list": user_ids,
                "operation_type": "APPEND",
            },
        )
        self._check_response(body, "upload_audience_users")
        return body["data"]

    # ══════════════════════════════════════════════════════════════
    # Tools / Targeting
    # ══════════════════════════════════════════════════════════════

    async def get_targeting_tags(
        self,
        tag_type: str = "INTEREST",
    ) -> list[dict]:
        """Get available targeting tags (interests, behaviors, etc.)."""
        params = self._account_params({"type": tag_type})
        body = await self.get(config.TARGETING_TAGS, params=params)
        self._check_response(body, "get_targeting_tags")
        return body.get("data", {}).get("list", [])

    async def estimate_reach(
        self,
        targeting: dict,
        site_set: list[str] | None = None,
    ) -> dict:
        """Estimate audience reach for given targeting."""
        json_data: dict[str, Any] = {"targeting": targeting}
        if site_set:
            json_data["site_set"] = site_set
        if self._account_id:
            json_data["account_id"] = self._account_id

        body = await self.post(config.ESTIMATE, json_data=json_data)
        self._check_response(body, "estimate_reach")
        return body["data"]
