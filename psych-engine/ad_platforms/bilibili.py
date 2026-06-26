"""哔哩哔哩(B站)广告平台适配器

商业平台: https://cm.bilibili.com/
API Base: https://api.bilibili.com/x/ad/
认证方式: API Key + Secret 签名
"""
import requests, hashlib, time, hmac, json
from .base import BaseAdPlatform, CampaignConfig, CreativeConfig, AdReport


BILI_API = "https://api.bilibili.com/x/ad"


class BilibiliAds(BaseAdPlatform):
    """哔哩哔哩商业广告平台"""

    def __init__(self, app_id: str = "", secret: str = "", access_token: str = ""):
        super().__init__("B站·哔哩哔哩", app_id, secret, access_token)

    def _sign(self, params: dict) -> str:
        """B站API签名: 参数排序+app_secret → MD5"""
        sorted_items = sorted(params.items())
        raw = "&".join(f"{k}={v}" for k, v in sorted_items)
        raw += self.app_secret
        return hashlib.md5(raw.encode()).hexdigest()

    def _headers(self) -> dict:
        ts = int(time.time())
        params = {"app_id": self.app_id, "ts": ts}
        sign = self._sign(params)
        return {
            "X-App-Id": self.app_id,
            "X-Timestamp": str(ts),
            "X-Sign": sign,
            "X-Access-Token": self.access_token,
            "Content-Type": "application/json",
        }

    def authenticate(self) -> bool:
        if not self.app_id or not self.app_secret:
            return False
        try:
            resp = requests.post(f"{BILI_API}/auth/token", headers={
                "Content-Type": "application/json",
            }, json={"app_id": self.app_id, "secret": self.app_secret}, timeout=10)
            data = resp.json()
            if data.get("code") == 0:
                self.access_token = data["data"]["access_token"]
                return True
            return False
        except Exception:
            return False

    def create_campaign(self, config: CampaignConfig) -> str:
        resp = requests.post(f"{BILI_API}/campaign/create",
                             headers=self._headers(), json={
            "campaign_name": config.name,
            "daily_budget": int(config.budget_daily * 100),
            "bid_type": config.bid_strategy.upper(),
        }, timeout=10)
        data = resp.json()
        if data.get("code") == 0:
            return str(data["data"]["campaign_id"])
        raise Exception(f"B站创建广告组失败: {data.get('message')}")

    def create_ad(self, campaign_id: str, creative: CreativeConfig) -> str:
        resp = requests.post(f"{BILI_API}/creative/create",
                             headers=self._headers(), json={
            "campaign_id": int(campaign_id),
            "title": creative.title,
            "description": creative.description,
            "image_url": creative.image_url or "",
            "video_url": creative.video_url or "",
            "landing_url": creative.landing_url,
            "cta": creative.cta_text,
        }, timeout=10)
        data = resp.json()
        if data.get("code") == 0:
            return str(data["data"]["creative_id"])
        raise Exception(f"B站创建素材失败: {data.get('message')}")

    def get_report(self, campaign_id: str,
                   start_date: str = "", end_date: str = "") -> AdReport:
        if not start_date:
            start_date = time.strftime("%Y-%m-%d", time.localtime(time.time()-86400))
        if not end_date:
            end_date = time.strftime("%Y-%m-%d")

        resp = requests.post(f"{BILI_API}/report/campaign",
                             headers=self._headers(), json={
            "campaign_id": int(campaign_id),
            "start_date": start_date,
            "end_date": end_date,
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
        resp = requests.post(f"{BILI_API}/campaign/update_budget",
                             headers=self._headers(), json={
            "campaign_id": int(campaign_id),
            "daily_budget": int(new_budget * 100),
        }, timeout=10)
        return resp.json().get("code") == 0

    def pause_campaign(self, campaign_id: str) -> bool:
        resp = requests.post(f"{BILI_API}/campaign/pause",
                             headers=self._headers(), json={
            "campaign_id": int(campaign_id),
        }, timeout=10)
        return resp.json().get("code") == 0

    def resume_campaign(self, campaign_id: str) -> bool:
        resp = requests.post(f"{BILI_API}/campaign/resume",
                             headers=self._headers(), json={
            "campaign_id": int(campaign_id),
        }, timeout=10)
        return resp.json().get("code") == 0
