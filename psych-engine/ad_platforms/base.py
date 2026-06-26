"""广告平台适配器基类"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import time, json


@dataclass
class CampaignConfig:
    """投放配置"""
    name: str
    budget_daily: float  # 日预算(元)
    bid_strategy: str = "ocpm"  # cpc/cpm/ocpm
    target_cpa: Optional[float] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    extra: dict = field(default_factory=dict)


@dataclass
class CreativeConfig:
    """素材配置"""
    title: str
    description: str
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    landing_url: str = ""
    cta_text: str = "了解更多"
    extra: dict = field(default_factory=dict)


@dataclass
class AdReport:
    """广告数据报告"""
    platform: str
    campaign_id: str
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0
    spend: float = 0.0
    revenue: float = 0.0  # 归因收入
    ctr: float = 0.0
    cvr: float = 0.0
    cpc: float = 0.0
    cpa: float = 0.0
    roi: float = 0.0

    def __post_init__(self):
        if self.impressions > 0:
            self.ctr = self.clicks / self.impressions
        if self.clicks > 0:
            self.cvr = self.conversions / self.clicks
            self.cpc = self.spend / self.clicks
        if self.conversions > 0:
            self.cpa = self.spend / self.conversions
        if self.spend > 0:
            self.roi = self.revenue / self.spend


class BaseAdPlatform(ABC):
    """广告平台基类"""

    def __init__(self, name: str, app_id: str = "", app_secret: str = "",
                 access_token: str = ""):
        self.name = name
        self.app_id = app_id
        self.app_secret = app_secret
        self.access_token = access_token

    @abstractmethod
    def authenticate(self) -> bool:
        """获取/刷新 access token"""
        ...

    @abstractmethod
    def create_campaign(self, config: CampaignConfig) -> str:
        """创建广告计划，返回 campaign_id"""
        ...

    @abstractmethod
    def create_ad(self, campaign_id: str, creative: CreativeConfig) -> str:
        """创建广告创意，返回 ad_id"""
        ...

    @abstractmethod
    def get_report(self, campaign_id: str,
                   start_date: str, end_date: str) -> AdReport:
        """获取广告数据报告"""
        ...

    @abstractmethod
    def update_budget(self, campaign_id: str, new_budget: float) -> bool:
        """调整预算"""
        ...

    @abstractmethod
    def pause_campaign(self, campaign_id: str) -> bool:
        """暂停广告"""
        ...

    @abstractmethod
    def resume_campaign(self, campaign_id: str) -> bool:
        """恢复广告"""
        ...

    def get_roi(self, campaign_id: str,
                start_date: str = "", end_date: str = "") -> float:
        """获取 ROI"""
        report = self.get_report(campaign_id, start_date, end_date)
        return report.roi

    def _log(self, action: str, detail: str):
        print(f"[{self.name}] {action}: {detail}")
