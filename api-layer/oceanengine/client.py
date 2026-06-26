"""
OceanEngine (巨量引擎) full API client.

This is the primary interface for 投投 to manage campaigns, ads,
creatives, reports, and audiences on OceanEngine.

Usage:
    auth = OceanEngineAuth(app_id="...", secret="...")
    await auth.get_token(auth_code="...")
    
    client = OceanEngineClient(auth)
    
    # Create campaign
    campaign = await client.create_campaign(
        advertiser_id="12345",
        name="人格测试-抖音投放-R1",
        budget=50000,  # 500元 in 分
    )
    
    # Pull report
    report = await client.get_ad_report(
        advertiser_id="12345",
        start_date="2026-06-20",
        end_date="2026-06-25",
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
from .auth import OceanEngineAuth
from . import config

logger = logging.getLogger("api-layer.oceanengine")


class OceanEngineClient(BaseClient):
    """Full OceanEngine Marketing API client."""

    BASE_URL = "https://api.oceanengine.com/open_api/"
    PLATFORM = "oceanengine"

    def __init__(
        self,
        auth: OceanEngineAuth,
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

    # ── Auth hooks ────────────────────────────────────────────────

    def _is_token_expired_error(self, response: httpx.Response, body: dict) -> bool:
        code = body.get("code", 0)
        return code in (40100, 40101, 40102)  # token expired/invalid codes

    async def _refresh_access_token(self) -> bool:
        if await self._auth.refresh():
            self._access_token = self._auth.access_token
            self._refresh_token = self._auth.refresh_token
            return True
        return False

    # ── Helpers ───────────────────────────────────────────────────

    def _require_advertiser(self, advertiser_id: str) -> str:
        if not advertiser_id:
            raise ValidationError("advertiser_id is required", platform=self.PLATFORM)
        return str(advertiser_id)

    def _date_str(self, d: date | str) -> str:
        if isinstance(d, date):
            return d.strftime("%Y-%m-%d")
        return d

    def _status_map(self, status: str) -> CampaignStatus:
        """Map OceanEngine status codes to unified model."""
        mapping = {
            "CAMPAIGN_STATUS_ENABLE": CampaignStatus.ACTIVE,
            "CAMPAIGN_STATUS_DISABLE": CampaignStatus.PAUSED,
            "CAMPAIGN_STATUS_DELETE": CampaignStatus.DELETED,
            "AD_STATUS_ENABLE": CampaignStatus.ACTIVE,
            "AD_STATUS_DISABLE": CampaignStatus.PAUSED,
            "AD_STATUS_DELETE": CampaignStatus.DELETED,
        }
        return mapping.get(status, CampaignStatus.PENDING)

    def _check_response(self, body: dict, context: str = "request") -> None:
        """Check OceanEngine API response code."""
        code = body.get("code", -1)
        if code != 0:
            raise APIError(
                f"[{context}] OceanEngine error {code}: {body.get('message', 'unknown')}",
                platform=self.PLATFORM,
                response_body=str(body),
            )

    # ══════════════════════════════════════════════════════════════
    # Campaign (广告组)
    # ══════════════════════════════════════════════════════════════

    async def create_campaign(
        self,
        advertiser_id: str,
        name: str,
        budget: float,              # in 分 (e.g., 50000 fen = 500 RMB)
        budget_mode: str = "CAMPAIGN_BUDGET_MODE_DAY",
        landing_type: str = "LINK",  # or "APP", "ARTICLE", etc.
    ) -> Campaign:
        """Create a new campaign (广告组)."""
        advertiser_id = self._require_advertiser(advertiser_id)

        body = await self.post(
            config.CAMPAIGN_CREATE,
            json_data={
                "advertiser_id": int(advertiser_id),
                "campaign_name": name,
                "budget": budget,
                "budget_mode": budget_mode,
                "landing_type": landing_type,
            },
        )
        self._check_response(body, "create_campaign")

        data = body["data"]
        return Campaign(
            external_id=str(data["campaign_id"]),
            platform=Platform.OCEANENGINE,
            name=name,
            status=CampaignStatus.PENDING,
            budget=budget,
            budget_type="daily" if budget_mode.endswith("DAY") else "total",
            raw_data=data,
        )

    async def get_campaigns(
        self,
        advertiser_id: str,
        ids: Optional[list[str]] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> list[Campaign]:
        """List campaigns."""
        advertiser_id = self._require_advertiser(advertiser_id)

        params: dict[str, Any] = {
            "advertiser_id": int(advertiser_id),
            "page": page,
            "page_size": page_size,
        }
        if ids:
            params["campaign_ids"] = [int(i) for i in ids]
        if status:
            params["status"] = status

        body = await self.get(config.CAMPAIGN_LIST, params=params)
        self._check_response(body, "get_campaigns")

        return [
            Campaign(
                external_id=str(c["campaign_id"]),
                platform=Platform.OCEANENGINE,
                name=c["campaign_name"],
                status=self._status_map(c.get("campaign_status", "")),
                budget=c.get("budget", 0),
                budget_type="daily" if c.get("budget_mode") == "CAMPAIGN_BUDGET_MODE_DAY" else "total",
                raw_data=c,
            )
            for c in body.get("data", {}).get("list", [])
        ]

    async def update_campaign(
        self,
        advertiser_id: str,
        campaign_id: str,
        name: Optional[str] = None,
        budget: Optional[float] = None,
    ) -> dict:
        """Update campaign name or budget."""
        advertiser_id = self._require_advertiser(advertiser_id)
        json_data: dict[str, Any] = {
            "advertiser_id": int(advertiser_id),
            "campaign_id": int(campaign_id),
        }
        if name:
            json_data["campaign_name"] = name
        if budget is not None:
            json_data["budget"] = budget

        body = await self.post(config.CAMPAIGN_UPDATE, json_data=json_data)
        self._check_response(body, "update_campaign")
        return body["data"]

    # ══════════════════════════════════════════════════════════════
    # Ad (广告计划)
    # ══════════════════════════════════════════════════════════════

    async def create_ad(
        self,
        advertiser_id: str,
        campaign_id: str,
        name: str,
        # Targeting
        gender: Optional[str] = None,          # "GENDER_FEMALE" / "GENDER_MALE" / None
        age: Optional[list[str]] = None,       # ["AGE_BETWEEN_18_23", "AGE_BETWEEN_24_30", ...]
        city: Optional[list[str]] = None,      # city codes
        interests: Optional[list[str]] = None,  # interest tag IDs
        # Bidding
        bid_type: str = "OBID_CPM",            # OCPM, CPC, CPM
        bid_amount: float = 10000,             # in 分/千次展示 (OCPM bid)
        # Budget
        daily_budget: Optional[float] = None,  # in 分
        # Schedule
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        # Creative
        creative_ids: Optional[list[str]] = None,
    ) -> dict:
        """Create an ad group (广告计划)."""
        advertiser_id = self._require_advertiser(advertiser_id)

        targeting: dict = {}
        if gender:
            targeting["gender"] = gender
        if age:
            targeting["age"] = age
        if city:
            targeting["city"] = city
        if interests:
            targeting["interest_tags"] = interests

        json_data: dict[str, Any] = {
            "advertiser_id": int(advertiser_id),
            "campaign_id": int(campaign_id),
            "name": name,
            "bid_type": bid_type,
            "pricing": bid_amount,
        }
        
        if targeting:
            json_data["targeting"] = targeting
        if daily_budget:
            json_data["budget"] = daily_budget
            json_data["budget_mode"] = "AD_BUDGET_MODE_DAY"
        if start_time:
            json_data["start_time"] = start_time.strftime("%Y-%m-%d %H:%M:%S")
        if end_time:
            json_data["end_time"] = end_time.strftime("%Y-%m-%d %H:%M:%S")
        if creative_ids:
            json_data["creative_ids"] = [int(cid) for cid in creative_ids]

        body = await self.post(config.AD_CREATE, json_data=json_data)
        self._check_response(body, "create_ad")
        return body["data"]

    async def update_ad_bid(
        self,
        advertiser_id: str,
        ad_id: str,
        bid_amount: float,
    ) -> dict:
        """Update ad bid amount."""
        body = await self.post(
            config.AD_BID_UPDATE,
            json_data={
                "advertiser_id": int(advertiser_id),
                "ad_id": int(ad_id),
                "data": [{"bid": bid_amount}],
            },
        )
        self._check_response(body, "update_ad_bid")
        return body["data"]

    async def update_ad_status(
        self,
        advertiser_id: str,
        ad_id: str,
        status: str,  # "AD_STATUS_ENABLE" / "AD_STATUS_DISABLE" / "AD_STATUS_DELETE"
    ) -> dict:
        """Enable, pause, or delete an ad."""
        body = await self.post(
            config.AD_STATUS_UPDATE,
            json_data={
                "advertiser_id": int(advertiser_id),
                "ad_ids": [int(ad_id)],
                "opt_status": status,
            },
        )
        self._check_response(body, "update_ad_status")
        return body["data"]

    # ══════════════════════════════════════════════════════════════
    # Creative (广告创意)
    # ══════════════════════════════════════════════════════════════

    async def create_creative(
        self,
        advertiser_id: str,
        ad_id: str,
        title: str,
        image_ids: list[str],
        landing_page_url: str,
        creative_type: str = "CREATIVE_IMAGE_MODE_LARGE_IMAGE",
    ) -> Creative:
        """Create a creative (single-image for simplicity; video support TBD)."""
        advertiser_id = self._require_advertiser(advertiser_id)

        body = await self.post(
            config.CREATIVE_CREATE,
            json_data={
                "advertiser_id": int(advertiser_id),
                "ad_id": int(ad_id),
                "creative_type": creative_type,
                "title": title,
                "image_ids": image_ids,
                "landing_page_url": landing_page_url,
            },
        )
        self._check_response(body, "create_creative")

        data = body["data"]
        return Creative(
            external_id=str(data.get("creative_id", "")),
            platform=Platform.OCEANENGINE,
            adgroup_id=ad_id,
            title=title,
            description="",
            image_urls=[],  # resolved via material/read
            landing_page_url=landing_page_url,
            raw_data=data,
        )

    async def get_creatives(
        self,
        advertiser_id: str,
        ad_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> list[Creative]:
        """List creatives, optionally filtered by ad."""
        advertiser_id = self._require_advertiser(advertiser_id)

        params: dict[str, Any] = {
            "advertiser_id": int(advertiser_id),
            "page": page,
            "page_size": page_size,
        }
        if ad_id:
            params["ad_id"] = int(ad_id)

        body = await self.get(config.CREATIVE_LIST, params=params)
        self._check_response(body, "get_creatives")

        return [
            Creative(
                external_id=str(c["creative_id"]),
                platform=Platform.OCEANENGINE,
                adgroup_id=str(c.get("ad_id", "")),
                title=c.get("title", ""),
                description=c.get("description", ""),
                image_urls=c.get("image_urls", []),
                landing_page_url=c.get("landing_page_url", ""),
                status=self._status_map(c.get("status", "")),
                raw_data=c,
            )
            for c in body.get("data", {}).get("list", [])
        ]

    # ══════════════════════════════════════════════════════════════
    # Reports (数据报表)
    # ══════════════════════════════════════════════════════════════

    async def get_ad_report(
        self,
        advertiser_id: str,
        start_date: date | str,
        end_date: date | str,
        ad_ids: Optional[list[str]] = None,
        group_by: str = "STAT_GROUP_BY_FIELD_STAT_TIME",  # daily aggregate
        page: int = 1,
        page_size: int = 100,
    ) -> list[ReportRow]:
        """Pull ad-level daily report.

        This is the primary data feed for 控控's real-time CPA monitoring
        and 投投's bid optimization.
        """
        advertiser_id = self._require_advertiser(advertiser_id)

        params: dict[str, Any] = {
            "advertiser_id": int(advertiser_id),
            "start_date": self._date_str(start_date),
            "end_date": self._date_str(end_date),
            "group_by": group_by,
            "page": page,
            "page_size": min(page_size, 200),
        }
        if ad_ids:
            params["ad_ids"] = [int(aid) for aid in ad_ids]

        body = await self.get(config.REPORT_AD, params=params)
        self._check_response(body, "get_ad_report")

        rows = []
        for r in body.get("data", {}).get("list", []):
            rows.append(ReportRow(
                platform=Platform.OCEANENGINE,
                date=r.get("stat_datetime", "")[:10],
                adgroup_id=str(r.get("ad_id", "")),
                campaign_id=str(r.get("campaign_id", "")),
                cost=r.get("stat_cost", 0) * 100,  # OceanEngine gives yuan, we store fen
                impressions=r.get("show_cnt", 0),
                clicks=r.get("click_cnt", 0),
                ctr=r.get("ctr", 0),
                cpm=r.get("stat_cost", 0) * 100,  # approximate
                cpc=r.get("cost_per_click", 0) * 100 if r.get("click_cnt", 0) > 0 else 0,
                conversions=r.get("convert_cnt", 0),
                conversion_cost=r.get("convert_cost", 0) * 100,
                conversion_rate=r.get("convert_rate", 0),
                raw_data=r,
            ))

        return rows

    async def get_campaign_report(
        self,
        advertiser_id: str,
        start_date: date | str,
        end_date: date | str,
        page: int = 1,
        page_size: int = 100,
    ) -> list[ReportRow]:
        """Pull campaign-level report."""
        advertiser_id = self._require_advertiser(advertiser_id)

        params: dict[str, Any] = {
            "advertiser_id": int(advertiser_id),
            "start_date": self._date_str(start_date),
            "end_date": self._date_str(end_date),
            "page": page,
            "page_size": min(page_size, 200),
        }

        body = await self.get(config.REPORT_CAMPAIGN, params=params)
        self._check_response(body, "get_campaign_report")

        rows = []
        for r in body.get("data", {}).get("list", []):
            rows.append(ReportRow(
                platform=Platform.OCEANENGINE,
                date=r.get("stat_datetime", "")[:10],
                campaign_id=str(r.get("campaign_id", "")),
                cost=r.get("stat_cost", 0) * 100,
                impressions=r.get("show_cnt", 0),
                clicks=r.get("click_cnt", 0),
                ctr=r.get("ctr", 0),
                cpm=r.get("stat_cost", 0) * 100,
                conversions=r.get("convert_cnt", 0),
                conversion_cost=r.get("convert_cost", 0) * 100,
                conversion_rate=r.get("convert_rate", 0),
                raw_data=r,
            ))

        return rows

    # ══════════════════════════════════════════════════════════════
    # DMP / Audiences (人群管理 — 析析→投投 的关键桥梁)
    # ══════════════════════════════════════════════════════════════

    async def push_audience(
        self,
        advertiser_id: str,
        audience_name: str,
        device_ids: list[str],       # IMEI/IDFA/OAID device IDs
        id_type: str = "IMEI_MD5",  # or "IDFA_MD5", "OAID_MD5"
    ) -> str:
        """Push a custom audience to OceanEngine DMP.

        This is how 析析's user segments become 投投's targeting:
        析析 analyzes users → segments → 荐荐 picks audience →
        投投 pushes to DMP → creates ad targeting that audience.

        Returns: audience_id
        """
        advertiser_id = self._require_advertiser(advertiser_id)

        body = await self.post(
            config.DMP_AUDIENCE_UPLOAD,
            json_data={
                "advertiser_id": int(advertiser_id),
                "name": audience_name,
                "id_type": id_type,
                "device_ids": device_ids,
            },
        )
        self._check_response(body, "push_audience")
        return str(body["data"]["audience_id"])

    async def get_audiences(
        self,
        advertiser_id: str,
    ) -> list[dict]:
        """List custom audiences for an advertiser."""
        advertiser_id = self._require_advertiser(advertiser_id)

        body = await self.get(
            config.DMP_AUDIENCE_LIST,
            params={"advertiser_id": int(advertiser_id)},
        )
        self._check_response(body, "get_audiences")
        return body.get("data", {}).get("custom_audience_list", [])

    # ══════════════════════════════════════════════════════════════
    # Tools
    # ══════════════════════════════════════════════════════════════

    async def suggest_bid(
        self,
        advertiser_id: str,
        targeting: Optional[dict] = None,
    ) -> dict:
        """Get bid suggestions for a given targeting."""
        params: dict[str, Any] = {
            "advertiser_id": int(advertiser_id),
        }
        if targeting:
            params["targeting"] = targeting

        body = await self.get(config.TOOLS_BID_SUGGEST, params=params)
        self._check_response(body, "suggest_bid")
        return body["data"]
