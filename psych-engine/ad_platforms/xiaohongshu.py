"""小红书(聚光平台)广告适配器

聚光平台: https://ad.xiaohongshu.com/
API Base: https://api.xiaohongshu.com/ad/
认证: OAuth 2.0 + API Key
"""
import requests, time, hashlib, json
from .base import BaseAdPlatform, CampaignConfig, CreativeConfig, AdReport


XHS_API = "https://api.xiaohongshu.com/ad"


class XiaohongshuAds(BaseAdPlatform):
    """小红书聚光广告平台"""

    def __init__(self, app_id: str = "", secret: str = "",
                 advertiser_id: str = "", access_token: str = ""):
        super().__init__("小红书·聚光", app_id, secret, access_token)
        self.advertiser_id = advertiser_id

    def authenticate(self) -> bool:
        if not self.app_id or not self.secret:
            return False
        try:
            resp = requests.post(f"{XHS_API}/oauth2/token", json={
                "app_id": self.app_id,
                "secret": self.secret,
                "grant_type": "client_credentials",
            }, timeout=10)
            data = resp.json()
            if data.get("code") == 0:
                self.access_token = data["data"]["access_token"]
                return True
            return False
        except Exception:
            return False

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def create_campaign(self, config: CampaignConfig) -> str:
        """小红书创建广告计划（笔记推广或信息流）"""
        resp = requests.post(f"{XHS_API}/v1/campaign/create",
                             headers=self._headers(), json={
            "advertiser_id": self.advertiser_id,
            "campaign_name": config.name,
            "daily_budget": int(config.budget_daily * 100),
            "campaign_type": "FEED",
            "bid_strategy": config.bid_strategy.upper(),
        }, timeout=10)
        data = resp.json()
        if data.get("code") == 0:
            return str(data["data"]["campaign_id"])
        raise Exception(f"小红书创建广告组失败: {data.get('message')}")

    def create_ad(self, campaign_id: str, creative: CreativeConfig) -> str:
        """创建小红书推广笔记"""
        resp = requests.post(f"{XHS_API}/v1/creative/create",
                             headers=self._headers(), json={
            "campaign_id": campaign_id,
            "title": creative.title[:20],  # 小红书标题限制
            "content": creative.description,
            "image_urls": [creative.image_url] if creative.image_url else [],
            "video_url": creative.video_url or "",
            "landing_url": creative.landing_url,
            "note_type": "VIDEO" if creative.video_url else "IMAGE",
        }, timeout=10)
        data = resp.json()
        if data.get("code") == 0:
            return str(data["data"]["creative_id"])
        raise Exception(f"小红书创建素材失败: {data.get('message')}")

    def get_report(self, campaign_id: str,
                   start_date: str = "", end_date: str = "") -> AdReport:
        """获取小红书广告报表"""
        if not start_date:
            start_date = time.strftime("%Y-%m-%d", time.localtime(time.time()-86400))
        if not end_date:
            end_date = time.strftime("%Y-%m-%d")

        resp = requests.post(f"{XHS_API}/v1/report/campaign",
                             headers=self._headers(), json={
            "advertiser_id": self.advertiser_id,
            "campaign_id": campaign_id,
            "start_date": start_date,
            "end_date": end_date,
            "metrics": ["impression", "click", "conversion", "cost",
                        "ctr", "cvr", "cpc", "cpa"],
        }, timeout=15)
        data = resp.json()
        report = AdReport(platform=self.name, campaign_id=campaign_id)
        if data.get("code") == 0 and data.get("data"):
            d = data["data"]
            report.impressions = d.get("impression", 0)
            report.clicks = d.get("click", 0)
            report.conversions = d.get("conversion", 0)
            report.spend = d.get("cost", 0) / 100
        return report

    def update_budget(self, campaign_id: str, new_budget: float) -> bool:
        resp = requests.post(f"{XHS_API}/v1/campaign/update_budget",
                             headers=self._headers(), json={
            "campaign_id": campaign_id,
            "daily_budget": int(new_budget * 100),
        }, timeout=10)
        return resp.json().get("code") == 0

    def pause_campaign(self, campaign_id: str) -> bool:
        resp = requests.post(f"{XHS_API}/v1/campaign/pause",
                             headers=self._headers(), json={
            "campaign_id": campaign_id,
        }, timeout=10)
        return resp.json().get("code") == 0

    def resume_campaign(self, campaign_id: str) -> bool:
        resp = requests.post(f"{XHS_API}/v1/campaign/resume",
                             headers=self._headers(), json={
            "campaign_id": campaign_id,
        }, timeout=10)
        return resp.json().get("code") == 0


class XiaohongshuCreatorAPI:
    """小红书创作者API（KOL/KOC 笔记合作）"""

    BASE = "https://api.xiaohongshu.com/creator"

    def __init__(self, access_token: str):
        self.token = access_token

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def get_note_analytics(self, note_id: str):
        """获取笔记数据"""
        resp = requests.get(f"{self.BASE}/v1/note/analytics",
                            headers=self._headers(),
                            params={"note_id": note_id}, timeout=10)
        return resp.json()

    def search_creators(self, keyword: str, limit: int = 20):
        """搜索创作者"""
        resp = requests.get(f"{self.BASE}/v1/creator/search",
                            headers=self._headers(),
                            params={"keyword": keyword, "limit": limit}, timeout=10)
        return resp.json()
