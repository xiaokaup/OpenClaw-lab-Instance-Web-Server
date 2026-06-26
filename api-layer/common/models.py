"""
Unified data models for cross-platform ad management.

These provide a platform-agnostic view that 投投 and 控控 work with.
Platform-specific clients translate their native responses into these models.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Platform(str, Enum):
    OCEANENGINE = "oceanengine"
    WECHAT_ADS = "wechat_ads"
    XIAOHONGSHU = "xiaohongshu"
    BILIBILI = "bilibili"


class CampaignStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    DELETED = "deleted"
    PENDING = "pending"


class BudgetType(str, Enum):
    DAILY = "daily"
    TOTAL = "total"
    UNLIMITED = "unlimited"


@dataclass
class Campaign:
    """Unified campaign (广告组/推广计划) model."""
    external_id: str
    platform: Platform
    name: str
    status: CampaignStatus
    budget: float                    # in 分 (RMB fen)
    budget_type: BudgetType
    daily_budget: Optional[float] = None   # in 分
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    raw_data: dict = field(default_factory=dict)


@dataclass
class AdGroup:
    """Unified ad group (广告计划) model."""
    external_id: str
    platform: Platform
    campaign_id: str
    name: str
    status: CampaignStatus
    bid_amount: float               # in 分
    bid_type: str                   # CPC, CPM, OCPM, etc.
    targeting: dict = field(default_factory=dict)
    daily_budget: Optional[float] = None
    raw_data: dict = field(default_factory=dict)


@dataclass
class Creative:
    """Unified creative (广告创意) model."""
    external_id: str
    platform: Platform
    adgroup_id: str
    title: str
    description: str
    image_urls: list[str] = field(default_factory=list)
    video_url: Optional[str] = None
    landing_page_url: str = ""
    status: CampaignStatus = CampaignStatus.ACTIVE
    raw_data: dict = field(default_factory=dict)


@dataclass
class ReportRow:
    """Unified report row (one row = one ad/day or adgroup/day)."""
    platform: Platform
    date: str                       # YYYY-MM-DD
    campaign_id: Optional[str] = None
    adgroup_id: Optional[str] = None
    creative_id: Optional[str] = None
    
    # Spend & delivery
    cost: float = 0.0               # in 分
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0                # click-through rate
    cpm: float = 0.0                # cost per mille (分)
    cpc: float = 0.0                # cost per click (分)
    
    # Conversions (filled when conversion tracking is set up)
    conversions: int = 0
    conversion_cost: float = 0.0    # CPA in 分
    conversion_rate: float = 0.0    # CVR
    
    raw_data: dict = field(default_factory=dict)
