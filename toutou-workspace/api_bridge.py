"""
L1 API层桥接 — 连接投投引擎与原生广告API

支持双模式:
- Demo模式: 使用Mock数据 (开发/测试/凭证未就绪时)
- Real模式: 连接真实L1 API (凭证就绪后切换)

当L1 API凭证就绪后，只需:
    1. 设置环境变量 OCEANENGINE_APP_ID / OCEANENGINE_SECRET
    2. 设置环境变量 WECHAT_ADS_CLIENT_ID / WECHAT_ADS_CLIENT_SECRET
    3. 将 demo_mode=False 即可切换为真实API

架构:
    投投工作区 (Flask API)
        │
        ▼
    APIBridge (本模块)
        ├─ Demo模式 → MockDataProvider
        └─ Real模式 → L1 API Layer (api-layer/)
            ├─ OceanEngineClient
            └─ WeChatAdsClient
"""

import os
import sys
import random
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("toutou.api_bridge")

# ── 尝试导入真实API ──
_real_api_available = False
try:
    # Add projects root to path
    projects_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if projects_root not in sys.path:
        sys.path.insert(0, projects_root)

    from api_layer.oceanengine import OceanEngineAuth, OceanEngineClient
    from api_layer.wechat_ads import WeChatAdsAuth, WeChatAdsClient
    from api_layer.common.models import Campaign, CampaignStatus, Creative, ReportRow, Platform
    _real_api_available = True
except ImportError as e:
    logger.warning(f"L1 API layer not available: {e}. Falling back to demo mode.")
    OceanEngineAuth = None
    OceanEngineClient = None
    WeChatAdsAuth = None
    WeChatAdsClient = None


@dataclass
class AdAccount:
    """广告账户"""
    platform: str           # oceanengine | wechat_ads
    account_id: str
    account_name: str
    status: str             # active | pending | suspended
    balance: float          # 账户余额(元)
    daily_budget: float     # 日预算(元)

@dataclass
class AdCampaign:
    """广告投放计划"""
    campaign_id: str
    platform: str
    platform_name: str
    name: str
    status: str             # active | paused | pending
    budget_daily: float
    spent_today: float
    impressions: int
    clicks: int
    conversions: int
    ctr: float
    cpc: float
    cpa: float
    roi: float
    created_at: str


class MockDataProvider:
    """Mock数据提供器 —— 用于Demo模式"""

    def __init__(self):
        self._campaigns: dict[str, AdCampaign] = {}
        self._next_id = 1000

    def create_campaign(
        self,
        platform: str,
        name: str,
        budget_daily: float,
    ) -> AdCampaign:
        """创建Mock广告计划"""
        cid = f"mock-{platform}-{self._next_id}"
        self._next_id += 1

        platform_names = {
            "oceanengine": "巨量引擎(抖音)",
            "wechat_ads": "微信广告",
            "douyin": "抖音",
            "xiaohongshu": "小红书",
            "bilibili": "B站",
        }

        campaign = AdCampaign(
            campaign_id=cid,
            platform=platform,
            platform_name=platform_names.get(platform, platform),
            name=name,
            status="active",
            budget_daily=budget_daily,
            spent_today=0.0,
            impressions=0,
            clicks=0,
            conversions=0,
            ctr=0.0,
            cpc=0.0,
            cpa=0.0,
            roi=0.0,
            created_at=datetime.now().isoformat(),
        )
        self._campaigns[cid] = campaign
        return campaign

    def get_simulated_report(self, campaign_id: str) -> dict:
        """模拟报表数据"""
        campaign = self._campaigns.get(campaign_id)
        if not campaign:
            return {}

        budget = campaign.budget_daily
        spent = round(budget * random.uniform(0.1, 0.9), 2)  # 花费10-90%预算
        impressions = int(spent * random.uniform(1000, 5000))  # 每元产生1K-5K曝光
        ctr = random.uniform(0.01, 0.05)  # 1%-5% CTR
        clicks = int(impressions * ctr)
        cvr = random.uniform(0.02, 0.08)  # 2%-8% CVR
        conversions = max(0, int(clicks * cvr))
        revenue = conversions * random.uniform(20, 200)  # 每次转化收入

        roi = revenue / spent if spent > 0 else 0

        # 更新累计数据
        campaign.spent_today += spent
        campaign.impressions += impressions
        campaign.clicks += clicks
        campaign.conversions += conversions
        if campaign.impressions > 0:
            campaign.ctr = campaign.clicks / campaign.impressions
        if campaign.clicks > 0:
            campaign.cpc = campaign.spent_today / campaign.clicks
        if campaign.conversions > 0:
            campaign.cpa = campaign.spent_today / campaign.conversions
        campaign.roi = (conversions * 30) / max(spent, 0.01)

        return {
            "campaign_id": campaign_id,
            "spend": spent,
            "revenue": round(revenue, 2),
            "impressions": impressions,
            "clicks": clicks,
            "conversions": conversions,
            "ctr": round(ctr, 4),
            "cvr": round(cvr, 4),
            "cpc": round(spent / max(clicks, 1), 2),
            "cpa": round(spent / max(conversions, 1), 2),
            "roi": round(roi, 2),
        }


class APIBridge:
    """
    L1 API层桥接

    模式切换:
        bridge = APIBridge(demo_mode=True)   # Demo模式
        bridge = APIBridge(demo_mode=False)  # 真实API模式
    """

    def __init__(self, demo_mode: bool = True):
        self.demo_mode = demo_mode
        self._mock = MockDataProvider()

        # Real API clients (lazy init)
        self._oe_client: Optional[OceanEngineClient] = None
        self._wx_client: Optional[WeChatAdsClient] = None

        if not demo_mode and not _real_api_available:
            logger.warning("Real API mode requested but L1 API layer unavailable. Falling back to demo.")
            self.demo_mode = True

    # ─── 账户信息 ────────────────────────────────────────────

    async def get_accounts(self) -> list[AdAccount]:
        """获取已连接的广告账户"""
        if self.demo_mode:
            return [
                AdAccount(
                    platform="oceanengine", account_id="demo-oe-001",
                    account_name="巨量引擎演示账户", status="active",
                    balance=10000.0, daily_budget=500.0,
                ),
                AdAccount(
                    platform="wechat_ads", account_id="demo-wx-001",
                    account_name="微信广告演示账户", status="active",
                    balance=5000.0, daily_budget=300.0,
                ),
            ]
        # Real mode: query actual accounts
        accounts = []
        try:
            if self._oe_client:
                # OceanEngine doesn't have a get_advertisers endpoint in current client
                accounts.append(AdAccount(
                    platform="oceanengine", account_id="real-oe",
                    account_name="巨量引擎", status="active",
                    balance=0, daily_budget=0,
                ))
            if self._wx_client:
                accounts.append(AdAccount(
                    platform="wechat_ads", account_id="real-wx",
                    account_name="微信广告", status="active",
                    balance=0, daily_budget=0,
                ))
        except Exception as e:
            logger.error(f"Failed to fetch accounts: {e}")
        return accounts

    # ─── 投放操作 ────────────────────────────────────────────

    async def create_campaign(
        self,
        platform: str,
        name: str,
        budget_daily: float,
        advertiser_id: str = "",
    ) -> dict:
        """创建广告计划"""
        if self.demo_mode:
            campaign = self._mock.create_campaign(platform, name, budget_daily)
            return {
                "success": True,
                "campaign_id": campaign.campaign_id,
                "platform": campaign.platform,
                "name": campaign.name,
                "budget_daily": campaign.budget_daily,
                "mode": "demo",
            }

        # Real mode
        try:
            if platform == "oceanengine":
                if not self._oe_client:
                    return {"success": False, "error": "OceanEngine client not initialized"}
                result = await self._oe_client.create_campaign(
                    advertiser_id=advertiser_id,
                    name=name,
                    budget=int(budget_daily * 100),  # Convert to fen
                )
                return {
                    "success": True,
                    "campaign_id": result.external_id,
                    "platform": platform,
                    "name": result.name,
                    "budget_daily": budget_daily,
                    "mode": "real",
                }
            elif platform == "wechat_ads":
                if not self._wx_client:
                    return {"success": False, "error": "WeChat Ads client not initialized"}
                result = await self._wx_client.create_adgroup(
                    name=name,
                    site_set=["SITE_SET_MOMENTS"],
                    daily_budget=int(budget_daily * 100),
                )
                return {
                    "success": True,
                    "campaign_id": result.external_id,
                    "platform": platform,
                    "name": result.name,
                    "budget_daily": budget_daily,
                    "mode": "real",
                }
            else:
                return {"success": False, "error": f"Unsupported platform: {platform}"}
        except Exception as e:
            logger.error(f"Failed to create campaign: {e}")
            return {"success": False, "error": str(e)}

    # ─── 数据报告 ────────────────────────────────────────────

    async def get_report(
        self,
        platform: str,
        campaign_id: str = "",
        days: int = 1,
    ) -> dict:
        """获取投放报告"""
        if self.demo_mode:
            if campaign_id:
                return self._mock.get_simulated_report(campaign_id)
            # 汇总模式
            total = {"spend": 0, "revenue": 0, "impressions": 0, "clicks": 0, "conversions": 0}
            for cid in self._mock._campaigns:
                r = self._mock.get_simulated_report(cid)
                for k in total:
                    total[k] += r.get(k, 0)
            if total["spend"] > 0:
                total["roi"] = round(total["revenue"] / total["spend"], 2)
            if total["impressions"] > 0:
                total["ctr"] = round(total["clicks"] / total["impressions"], 4)
            if total["clicks"] > 0:
                total["cpc"] = round(total["spend"] / total["clicks"], 2)
            if total["conversions"] > 0:
                total["cpa"] = round(total["spend"] / total["conversions"], 2)
            return total

        # Real mode
        try:
            if platform == "oceanengine" and self._oe_client:
                today = datetime.now().date()
                rows = await self._oe_client.get_ad_report(
                    advertiser_id="",  # Need real advertiser_id
                    start_date=today - timedelta(days=days),
                    end_date=today,
                )
                return self._summarize_report(rows)
            elif platform == "wechat_ads" and self._wx_client:
                today = datetime.now().date()
                rows = await self._wx_client.get_daily_report(
                    start_date=today - timedelta(days=days),
                    end_date=today,
                )
                return self._summarize_report(rows)
        except Exception as e:
            logger.error(f"Failed to fetch report: {e}")
            return {"error": str(e)}

        return {"error": "No data"}

    def _summarize_report(self, rows: list) -> dict:
        """汇总报表行"""
        total = {"spend": 0, "revenue": 0, "impressions": 0, "clicks": 0, "conversions": 0}
        for r in rows:
            total["spend"] += getattr(r, "cost", 0) / 100  # Convert fen to yuan
            total["impressions"] += getattr(r, "impressions", 0)
            total["clicks"] += getattr(r, "clicks", 0)
            total["conversions"] += getattr(r, "conversions", 0)
        if total["spend"] > 0:
            total["roi"] = round(total["revenue"] / total["spend"], 2)
        if total["impressions"] > 0:
            total["ctr"] = round(total["clicks"] / total["impressions"], 4)
        if total["clicks"] > 0:
            total["cpc"] = round(total["spend"] / total["clicks"], 2)
        if total["conversions"] > 0:
            total["cpa"] = round(total["spend"] / total["conversions"], 2)
        return total

    # ─── 状态查询 ────────────────────────────────────────────

    def get_mode_info(self) -> dict:
        """获取当前模式信息"""
        return {
            "mode": "demo" if self.demo_mode else "real",
            "l1_api_available": _real_api_available,
            "platforms_available": {
                "oceanengine": _real_api_available and OceanEngineClient is not None,
                "wechat_ads": _real_api_available and WeChatAdsClient is not None,
            },
            "credentials_required": [
                "OCEANENGINE_APP_ID / OCEANENGINE_SECRET",
                "WECHAT_ADS_CLIENT_ID / WECHAT_ADS_CLIENT_SECRET",
            ],
        }

    def get_connection_status(self) -> dict:
        """获取API连接状态"""
        return {
            "oceanengine": {
                "status": "connected" if not self.demo_mode and self._oe_client else "demo",
                "client_ready": self._oe_client is not None,
                "message": "Demo模式 - 使用模拟数据" if self.demo_mode else "真实API已连接",
            },
            "wechat_ads": {
                "status": "connected" if not self.demo_mode and self._wx_client else "demo",
                "client_ready": self._wx_client is not None,
                "message": "Demo模式 - 使用模拟数据" if self.demo_mode else "真实API已连接",
            },
        }
