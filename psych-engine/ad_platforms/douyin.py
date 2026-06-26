"""巨量引擎(抖音)广告平台适配器

API 文档: https://open.oceanengine.com/
认证方式: OAuth 2.0
Base URL: https://api.oceanengine.com/open_api/

核心接口:
- POST /oauth2/access_token/        获取token
- POST /2/campaign/create/          创建广告组
- POST /2/ad/create/                创建广告计划
- POST /2/report/advertiser/get/    获取报表
- POST /2/ad/update/budget/         更新预算
- POST /2/ad/update/status/         更新状态
"""
import requests
import hashlib
import time
import json
from .base import BaseAdPlatform, CampaignConfig, CreativeConfig, AdReport


OCEAN_API = "https://api.oceanengine.com/open_api"


class DouyinAds(BaseAdPlatform):
    """巨量引擎(抖音+头条+西瓜+火山)广告平台"""

    def __init__(self, app_id: str = "", secret: str = "",
                 advertiser_id: str = "", access_token: str = "",
                 refresh_token: str = ""):
        super().__init__("抖音·巨量引擎", app_id, secret, access_token)
        self.advertiser_id = advertiser_id
        self.refresh_token = refresh_token

    # ======== 认证 ========

    def authenticate(self) -> bool:
        """OAuth 2.0 获取 access_token"""
        if not self.app_id or not self.secret:
            self._log("认证", "缺少 app_id/secret, 使用模拟模式")
            return False

        try:
            resp = requests.post(f"{OCEAN_API}/oauth2/access_token/", json={
                "app_id": self.app_id,
                "secret": self.secret,
                "grant_type": "auth_code",
                "auth_code": self.access_token or "",
            }, timeout=10)
            data = resp.json()
            if data.get("code") == 0:
                self.access_token = data["data"]["access_token"]
                self.refresh_token = data["data"].get("refresh_token", "")
                self._log("认证", "access_token 获取成功")
                return True
            self._log("认证失败", str(data.get("message", "")))
            return False
        except Exception as e:
            self._log("认证异常", str(e))
            return False

    def _headers(self) -> dict:
        return {
            "Access-Token": self.access_token,
            "Content-Type": "application/json",
        }

    # ======== 投放管理 ========

    def create_campaign(self, config: CampaignConfig) -> str:
        """创建广告组"""
        resp = requests.post(f"{OCEAN_API}/2/campaign/create/",
                             headers=self._headers(), json={
            "advertiser_id": self.advertiser_id,
            "campaign_name": config.name,
            "budget_mode": "BUDGET_MODE_DAY",
            "budget": config.budget_daily * 100,  # 转换为分
            "campaign_type": "FEED",
        }, timeout=10)
        data = resp.json()
        if data.get("code") == 0:
            cid = str(data["data"]["campaign_id"])
            self._log("创建广告组", f"cid={cid}, budget=¥{config.budget_daily}")
            return cid
        raise Exception(f"巨量引擎创建广告组失败: {data.get('message')}")

    def create_ad(self, campaign_id: str, creative: CreativeConfig) -> str:
        """创建广告计划+创意"""
        # 先创建广告计划
        resp = requests.post(f"{OCEAN_API}/2/ad/create/",
                             headers=self._headers(), json={
            "advertiser_id": self.advertiser_id,
            "campaign_id": int(campaign_id),
            "ad_name": creative.title[:50],
            "delivery_range": "UNIVERSAL",
            "pricing": "OCPM",
            "budget": 0,
        }, timeout=10)
        data = resp.json()
        if data.get("code") != 0:
            raise Exception(f"巨量引擎创建广告计划失败: {data.get('message')}")
        ad_id = str(data["data"]["ad_id"])
        self._log("创建广告", f"ad_id={ad_id}, title={creative.title[:30]}")
        return ad_id

    # ======== 数据报表 ========

    def get_report(self, campaign_id: str,
                   start_date: str = "", end_date: str = "") -> AdReport:
        """获取广告数据报表"""
        if not start_date:
            start_date = time.strftime("%Y-%m-%d", time.localtime(time.time()-86400))
        if not end_date:
            end_date = time.strftime("%Y-%m-%d")

        resp = requests.post(f"{OCEAN_API}/2/report/advertiser/get/",
                             headers=self._headers(), json={
            "advertiser_id": self.advertiser_id,
            "start_date": start_date,
            "end_date": end_date,
            "filtering": {"campaign_ids": [int(campaign_id)]},
            "fields": ["impression", "click", "convert", "cost", "stat_cost"],
        }, timeout=15)
        data = resp.json()
        report = AdReport(platform=self.name, campaign_id=campaign_id)
        if data.get("code") == 0 and data["data"].get("list"):
            row = data["data"]["list"][0]
            report.impressions = row.get("impression", 0)
            report.clicks = row.get("click", 0)
            report.conversions = row.get("convert", 0)
            report.spend = row.get("stat_cost", 0) / 100
        return report

    # ======== 预算与状态 ========

    def update_budget(self, campaign_id: str, new_budget: float) -> bool:
        resp = requests.post(f"{OCEAN_API}/2/ad/update/budget/",
                             headers=self._headers(), json={
            "advertiser_id": self.advertiser_id,
            "data": [{"ad_id": int(campaign_id),
                       "budget": new_budget * 100}],
        }, timeout=10)
        return resp.json().get("code") == 0

    def pause_campaign(self, campaign_id: str) -> bool:
        resp = requests.post(f"{OCEAN_API}/2/ad/update/status/",
                             headers=self._headers(), json={
            "advertiser_id": self.advertiser_id,
            "ad_ids": [int(campaign_id)],
            "opt_status": "DISABLE",
        }, timeout=10)
        return resp.json().get("code") == 0

    def resume_campaign(self, campaign_id: str) -> bool:
        resp = requests.post(f"{OCEAN_API}/2/ad/update/status/",
                             headers=self._headers(), json={
            "advertiser_id": self.advertiser_id,
            "ad_ids": [int(campaign_id)],
            "opt_status": "ENABLE",
        }, timeout=10)
        return resp.json().get("code") == 0
