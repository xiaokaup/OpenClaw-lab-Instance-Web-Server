"""模拟广告平台 —— 无真实API密钥时的 Demo 模式"""
import random, time, json
from .base import BaseAdPlatform, CampaignConfig, CreativeConfig, AdReport


class MockAdPlatform(BaseAdPlatform):
    """模拟广告平台 —— 返回真实感数据用于测试"""

    def __init__(self, name: str = "模拟平台"):
        super().__init__(f"Mock·{name}")
        self._campaigns = {}
        self._ctr_base = random.uniform(0.01, 0.05)
        self._cvr_base = random.uniform(0.01, 0.06)

    def authenticate(self) -> bool:
        return True

    def create_campaign(self, config: CampaignConfig) -> str:
        cid = f"mock-{self.name}-{int(time.time()*1000)}"
        self._campaigns[cid] = {
            "config": config,
            "start_time": time.time(),
            "spend": 0.0,
            "impressions": 0,
            "clicks": 0,
            "conversions": 0,
        }
        return cid

    def create_ad(self, campaign_id: str, creative: CreativeConfig) -> str:
        aid = f"ad-{campaign_id}-{random.randint(1000,9999)}"
        return aid

    def get_report(self, campaign_id: str,
                   start_date: str = "", end_date: str = "") -> AdReport:
        """生成模拟数据——有真实统计规律的随机数据"""
        camp = self._campaigns.get(campaign_id, {})
        config = camp.get("config")
        budget = config.budget_daily if config else 100

        # 基于日预算模拟曝光量
        impressions = int(budget * random.uniform(15, 50))
        ctr = self._ctr_base * random.uniform(0.7, 1.4)
        clicks = int(impressions * ctr)
        cvr = self._cvr_base * random.uniform(0.6, 1.5)
        conversions = max(1, int(clicks * cvr))
        cpc = random.uniform(1, 10)
        spend = round(clicks * cpc, 2)
        revenue = round(conversions * random.uniform(30, 300), 2)

        # 更新累计
        if campaign_id in self._campaigns:
            self._campaigns[campaign_id]["spend"] += spend
            self._campaigns[campaign_id]["impressions"] += impressions
            self._campaigns[campaign_id]["clicks"] += clicks
            self._campaigns[campaign_id]["conversions"] += conversions

        return AdReport(
            platform=self.name,
            campaign_id=campaign_id,
            impressions=impressions,
            clicks=clicks,
            conversions=conversions,
            spend=spend,
            revenue=revenue,
        )

    def update_budget(self, campaign_id: str, new_budget: float) -> bool:
        if campaign_id in self._campaigns:
            self._campaigns[campaign_id]["config"].budget_daily = new_budget
            return True
        return False

    def pause_campaign(self, campaign_id: str) -> bool:
        return True

    def resume_campaign(self, campaign_id: str) -> bool:
        return True
