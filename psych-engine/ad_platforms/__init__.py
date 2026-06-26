"""广告平台统一管理层 —— 心因引擎渠道分发层的执行端"""
import os, json, time
from typing import Optional
from .base import BaseAdPlatform, CampaignConfig, CreativeConfig, AdReport
from .douyin import DouyinAds
from .bilibili import BilibiliAds
from .xiaohongshu import XiaohongshuAds
from .mock import MockAdPlatform


# ============ 渠道 → 平台映射 ============

CHANNEL_PLATFORM = {
    "douyin": "douyin",
    "bilibili": "bilibili",
    "xiaohongshu": "xiaohongshu",
    # 非广告平台的渠道
    "zhihu": None,
    "wechat": None,
    "weibo": None,
}


class AdManager:
    """
    统一广告管理

    用法:
        mgr = AdManager(demo=True)  # demo模式用Mock数据

        # 根据心因引擎渠道策略创建投放
        cid = mgr.launch(
            channel="douyin",
            name="心理测试-深度思考者-知乎引流",
            budget=200,
            creative={"title": "...", "description": "...", "cta": "立即测试"}
        )

        # 获取ROI
        roi = mgr.get_roi(cid, channel="douyin")

        # 预算分配师自动调整
        mgr.rebalance({"douyin": 300, "bilibili": 150, "xiaohongshu": 50})
    """

    def __init__(self, demo: bool = False,
                 credentials: Optional[dict] = None):
        """
        credentials = {
            "douyin": {"app_id": "", "secret": "", "advertiser_id": ""},
            "bilibili": {"app_id": "", "secret": ""},
            "xiaohongshu": {"app_id": "", "secret": "", "advertiser_id": ""},
        }
        """
        self.demo = demo
        self.credentials = credentials or {}

        # 初始化平台实例
        self._platforms = {}
        self._init_platforms()

        # 投放记录
        self._campaigns = {}   # {campaign_id: {channel, platform, budget}}

    def _init_platforms(self):
        """初始化各平台适配器"""
        if self.demo:
            self._platforms = {
                "douyin": MockAdPlatform("抖音"),
                "bilibili": MockAdPlatform("B站"),
                "xiaohongshu": MockAdPlatform("小红书"),
            }
            return

        creds = self.credentials

        # 抖音
        dy = creds.get("douyin", {})
        if dy.get("app_id"):
            self._platforms["douyin"] = DouyinAds(
                app_id=dy["app_id"], secret=dy.get("secret", ""),
                advertiser_id=dy.get("advertiser_id", ""),
            )

        # B站
        bl = creds.get("bilibili", {})
        if bl.get("app_id"):
            self._platforms["bilibili"] = BilibiliAds(
                app_id=bl["app_id"], secret=bl.get("secret", ""),
            )

        # 小红书
        xhs = creds.get("xiaohongshu", {})
        if xhs.get("app_id"):
            self._platforms["xiaohongshu"] = XiaohongshuAds(
                app_id=xhs["app_id"], secret=xhs.get("secret", ""),
                advertiser_id=xhs.get("advertiser_id", ""),
            )

        # 对没配置的渠道使用 Mock
        for ch in ["douyin", "bilibili", "xiaohongshu"]:
            if ch not in self._platforms:
                self._platforms[ch] = MockAdPlatform(
                    {"douyin": "抖音", "bilibili": "B站", "xiaohongshu": "小红书"}[ch]
                )

    def get_platform(self, channel: str) -> Optional[BaseAdPlatform]:
        """获取渠道对应的广告平台"""
        platform_key = CHANNEL_PLATFORM.get(channel)
        if not platform_key:
            return None
        return self._platforms.get(platform_key)

    # ============ 投放操作 ============

    def launch(self, channel: str, name: str, budget: float,
               creative_data: dict) -> Optional[str]:
        """
        在指定渠道创建广告投放

        Args:
            channel: douyin/bilibili/xiaohongshu
            name: 广告名称
            budget: 日预算(元)
            creative_data: {title, description, image_url?, video_url?, landing_url?, cta?}

        Returns:
            campaign_id 或 None（渠道不支持广告投放）
        """
        platform = self.get_platform(channel)
        if not platform:
            print(f"[AdManager] 渠道 {channel} 没有对应的广告平台，跳过")
            return None

        # 创建广告组
        config = CampaignConfig(
            name=name[:50],
            budget_daily=budget,
            bid_strategy="ocpm",
        )
        cid = platform.create_campaign(config)

        # 创建素材
        creative = CreativeConfig(
            title=creative_data.get("title", name),
            description=creative_data.get("description", ""),
            image_url=creative_data.get("image_url"),
            video_url=creative_data.get("video_url"),
            landing_url=creative_data.get("landing_url", ""),
            cta_text=creative_data.get("cta", "了解更多"),
        )
        platform.create_ad(cid, creative)

        # 记录
        self._campaigns[cid] = {
            "channel": channel,
            "platform": platform.name,
            "budget": budget,
            "name": name,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        print(f"[AdManager] 🚀 投放上线: {channel} | {name} | ¥{budget}/天 | cid={cid}")
        return cid

    def get_roi(self, campaign_id: str, channel: str = "") -> float:
        """获取投放ROI"""
        platform = None
        if channel:
            platform = self.get_platform(channel)
        if not platform and campaign_id in self._campaigns:
            platform = self.get_platform(self._campaigns[campaign_id]["channel"])
        if not platform:
            return 0.0

        report = platform.get_report(campaign_id)
        return report.roi

    def get_all_reports(self) -> list[AdReport]:
        """获取所有活跃投放的数据"""
        reports = []
        for cid, info in self._campaigns.items():
            platform = self.get_platform(info["channel"])
            if platform:
                report = platform.get_report(cid)
                reports.append(report)
        return reports

    # ============ 预算管理 ============

    def rebalance(self, allocation: dict):
        """
        按预算分配方案调整各渠道预算

        allocation = {"douyin": 300, "bilibili": 150, "xiaohongshu": 50}
        """
        for channel, budget in allocation.items():
            # 找到该渠道的活跃投放
            for cid, info in self._campaigns.items():
                if info["channel"] == channel:
                    platform = self.get_platform(channel)
                    if platform:
                        platform.update_budget(cid, budget)
                        old = info["budget"]
                        info["budget"] = budget
                        print(f"[AdManager] 📊 {channel}: ¥{old}→¥{budget}/天 (cid={cid})")

    def pause_channel(self, channel: str):
        """暂停某渠道全部投放"""
        for cid, info in self._campaigns.items():
            if info["channel"] == channel:
                platform = self.get_platform(channel)
                if platform:
                    platform.pause_campaign(cid)
                    print(f"[AdManager] ⏸ 暂停: {channel} (cid={cid})")

    def status(self) -> dict:
        """投放状态总览"""
        total_budget = sum(c["budget"] for c in self._campaigns.values())
        channels = {}
        for cid, info in self._campaigns.items():
            ch = info["channel"]
            if ch not in channels:
                channels[ch] = {"budget": 0, "count": 0, "campaigns": []}
            channels[ch]["budget"] += info["budget"]
            channels[ch]["count"] += 1
            channels[ch]["campaigns"].append({
                "cid": cid, "name": info["name"], "budget": info["budget"],
                "created": info["created_at"],
            })

        return {
            "demo_mode": self.demo,
            "active_platforms": list(self._platforms.keys()),
            "total_budget_daily": total_budget,
            "channels": channels,
        }
