"""
出价优化引擎 — 智能出价 + 自动调优

核心功能:
- 基于目标(转化/曝光/点击)推荐出价策略
- 成本约束下的最优出价
- A/B对照组出价差异设计
- 自动调价规则 (涨/降/停)

出价模式:
- OCPM: 优化千次展示成本 (推荐)
- CPC: 按点击付费
- CPM: 按展示付费
- OCPC: 优化点击成本
"""

from dataclasses import dataclass, field
from typing import Optional, Literal


BidMode = Literal["OCPM", "CPC", "CPM", "OCPC"]


@dataclass
class BidStrategy:
    """出价策略"""
    mode: str                    # OCPM/CPC/CPM/OCPC
    bid_amount: float           # 出价(元)
    target_cpa: float           # 目标CPA(元)
    target_roi: float           # 目标ROI
    daily_budget: float         # 日预算(元)
    # 自动调价规则
    auto_rules: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class BidRecommendation:
    """出价建议"""
    channel: str
    channel_name: str
    strategies: list[BidStrategy]
    recommended: str            # 推荐策略的描述
    confidence: float           # 建议置信度 (0-1)
    market_range: tuple[float, float]  # 市场出价范围


class BidOptimizer:
    """
    出价优化引擎

    用法:
        optimizer = BidOptimizer()
        recs = optimizer.optimize(
            channel="douyin",
            goal="conversion",
            daily_budget=500,
            target_cpa=30,
        )
    """

    # ── 行业出价基准 (2026年) ──────────────────────────────

    MARKET_BENCHMARKS: dict[str, dict] = {
        "douyin": {
            "cpc": (0.5, 3.0),
            "cpm": (20, 80),
            "ocpm_conversion": (60, 150),  # 优化转化的OCPM出价范围
            "ocpm_click": (30, 80),        # 优化点击的OCPM出价范围
            "cpa_target": (15, 60),        # 目标CPA范围
            "conversion_rate": 0.03,       # 行业平均CVR (3%)
        },
        "xiaohongshu": {
            "cpc": (0.3, 2.0),
            "cpm": (15, 50),
            "ocpm_conversion": (40, 100),
            "ocpm_click": (20, 60),
            "cpa_target": (10, 40),
            "conversion_rate": 0.04,
        },
        "bilibili": {
            "cpc": (0.8, 4.0),
            "cpm": (25, 100),
            "ocpm_conversion": (80, 200),
            "ocpm_click": (40, 100),
            "cpa_target": (20, 80),
            "conversion_rate": 0.02,
        },
        "wechat_moments": {
            "cpc": (1.0, 5.0),
            "cpm": (30, 120),
            "ocpm_conversion": (80, 200),
            "ocpm_click": (40, 120),
            "cpa_target": (20, 80),
            "conversion_rate": 0.02,
        },
        "zhihu": {
            "cpc": (1.0, 5.0),
            "cpm": (20, 60),
            "ocpm_conversion": (50, 150),
            "ocpm_click": (30, 80),
            "cpa_target": (15, 60),
            "conversion_rate": 0.03,
        },
        "weibo": {
            "cpc": (0.3, 1.5),
            "cpm": (10, 40),
            "ocpm_conversion": (30, 90),
            "ocpm_click": (15, 50),
            "cpa_target": (8, 35),
            "conversion_rate": 0.02,
        },
    }

    # ── 渠道名称映射 ──

    CHANNEL_NAMES: dict[str, str] = {
        "douyin": "抖音",
        "xiaohongshu": "小红书",
        "bilibili": "B站",
        "wechat_moments": "微信朋友圈",
        "zhihu": "知乎",
        "weibo": "微博",
        "oceanengine": "巨量引擎(抖音)",
        "wechat_ads": "微信广告",
    }

    def optimize(
        self,
        channel: str,
        goal: str = "conversion",   # conversion | traffic | awareness
        daily_budget: float = 500,
        target_cpa: float = 30.0,    # 目标CPA(元)
        target_roi: float = 2.0,     # 目标ROI
        is_new_campaign: bool = True,
        competition_level: str = "medium",  # low | medium | high
    ) -> BidRecommendation:
        """
        为指定渠道生成出价建议

        Args:
            channel: 渠道key
            goal: 投放目标
            daily_budget: 日预算
            target_cpa: 目标CPA
            target_roi: 目标ROI
            is_new_campaign: 是否新计划
            competition_level: 竞争程度
        """
        benchmarks = self.MARKET_BENCHMARKS.get(channel)
        if not benchmarks:
            return BidRecommendation(
                channel=channel,
                channel_name=self.CHANNEL_NAMES.get(channel, channel),
                strategies=[],
                recommended=f"渠道 {channel} 暂无出价数据",
                confidence=0.0,
                market_range=(0, 0),
            )

        strategies = []
        channel_name = self.CHANNEL_NAMES.get(channel, channel)

        # ── 策略1: OCPM (推荐) ──
        if goal == "conversion":
            ocpm_low, ocpm_high = benchmarks["ocpm_conversion"]
            # 根据竞争程度调整出价
            competition_mult = {"low": 0.7, "medium": 1.0, "high": 1.3}[competition_level]
            # 新计划建议偏高起步
            new_campaign_mult = 1.15 if is_new_campaign else 1.0

            bid_amount = round((ocpm_low + ocpm_high) / 2 * competition_mult * new_campaign_mult, 0)

            strategies.append(BidStrategy(
                mode="OCPM",
                bid_amount=bid_amount,
                target_cpa=target_cpa,
                target_roi=target_roi,
                daily_budget=daily_budget,
                auto_rules=[
                    {
                        "condition": f"CPA > ¥{target_cpa * 1.5:.0f} 持续2小时",
                        "action": "降价20%",
                        "reason": "成本超出目标50%",
                    },
                    {
                        "condition": f"CPA < ¥{target_cpa * 0.7:.0f} 持续4小时",
                        "action": "加价15%",
                        "reason": "成本低于目标，可以放量",
                    },
                    {
                        "condition": "花费>¥150 且0转化",
                        "action": "暂停计划",
                        "reason": "无转化信号，素材或定向有问题",
                    },
                ],
                notes=[
                    f"建议起始出价 ¥{bid_amount:.0f}/千次展示",
                    f"预期CPA ¥{target_cpa} (设置目标成本为 ¥{target_cpa:.0f})",
                    "OCPM模式下系统会自动优化，冷启动期(0-50个转化)不要频繁调价",
                ],
            ))

        # ── 策略2: CPC (稳健型) ──
        cpc_low, cpc_high = benchmarks["cpc"]
        bid_amount_cpc = round((cpc_low + cpc_high) / 2, 1)

        strategies.append(BidStrategy(
            mode="CPC",
            bid_amount=bid_amount_cpc,
            target_cpa=target_cpa,
            target_roi=target_roi,
            daily_budget=daily_budget,
            auto_rules=[
                {
                    "condition": f"CTR < 1% 持续24小时",
                    "action": "更换素材",
                    "reason": "CTR过低，素材不吸引人",
                },
                {
                    "condition": f"CPC > ¥{cpc_high} 持续4小时",
                    "action": "降价15%",
                    "reason": "CPC超出市场均价",
                },
            ],
            notes=[
                "CPC模式适合素材测试期",
                "OCPM跑通后(50+转化)应切换为OCPM以获得更优成本",
                f"预期CTR {benchmarks['conversion_rate']*100:.0f}%，实际转化成本取决于落地页",
            ],
        ))

        # ── 策略3: 激进型(新渠道抢量) ──
        if is_new_campaign and competition_level == "high":
            strategies.append(BidStrategy(
                mode="OCPM",
                bid_amount=round(benchmarks["ocpm_conversion"][1] * 1.1, 0),
                target_cpa=target_cpa * 1.3,
                target_roi=target_roi * 0.8,
                daily_budget=daily_budget * 0.5,  # 先用50%预算试探
                auto_rules=[
                    {
                        "condition": "CPA > ¥{:.0f} 持续1小时".format(target_cpa * 2),
                        "action": "急停",
                        "reason": "成本严重超预算",
                    },
                    {
                        "condition": "CPA < ¥{:.0f} 持续3小时".format(target_cpa),
                        "action": "放量至¥{:.0f}/天".format(daily_budget),
                        "reason": "成本达标，可追加预算",
                    },
                ],
                notes=[
                    "激进策略，用于新渠道抢量",
                    "建议最多跑24小时，无效则停",
                    f"预算设上限¥{daily_budget * 0.5:.0f}/天以防失控",
                ],
            ))

        # 推荐策略
        if goal == "conversion":
            recommended = f"推荐OCPM出价 ¥{strategies[0].bid_amount:.0f}/千次展示，目标CPA ¥{target_cpa}/转化"
        else:
            recommended = f"推荐CPC出价 ¥{bid_amount_cpc}，适合素材测试和流量积累"

        return BidRecommendation(
            channel=channel,
            channel_name=channel_name,
            strategies=strategies,
            recommended=recommended,
            confidence=0.75 if is_new_campaign else 0.85,
            market_range=(
                benchmarks["ocpm_conversion"][0] if goal == "conversion" else benchmarks["cpc"][0],
                benchmarks["ocpm_conversion"][1] if goal == "conversion" else benchmarks["cpc"][1],
            ),
        )

    def compare_channels(
        self,
        channels: list[str],
        daily_budget: float = 500,
        target_cpa: float = 30.0,
    ) -> list[BidRecommendation]:
        """对比多个渠道的出价建议"""
        return [
            self.optimize(ch, goal="conversion", daily_budget=daily_budget, target_cpa=target_cpa)
            for ch in channels
        ]

    def get_auto_adjust_rules(self, campaign_days: int = 0) -> list[dict]:
        """获取自动调价规则集"""
        if campaign_days < 3:
            # 冷启动期
            return [
                {"rule": "冷启动保护", "condition": "花费 < ¥100 或 转化 < 10", "action": "不做自动调价，等待模型学习"},
                {"rule": "异常防护", "condition": "单小时CPA > 目标的300%", "action": "降价50% 或 暂停计划"},
            ]
        else:
            # 稳定期
            return [
                {"rule": "成本控制", "condition": "过去24h CPA > 目标120%", "action": "降价15%"},
                {"rule": "放量策略", "condition": "过去24h CPA < 目标80% 且 预算耗尽", "action": "加价10% + 追加预算20%"},
                {"rule": "时段优化", "condition": "特定时段CPA比均值高50%", "action": "该时段降价30%"},
                {"rule": "素材衰减", "condition": "同一素材CTR连续3天下降", "action": "触发素材替换"},
            ]

    def suggest_bid_adjustment(
        self,
        current_bid: float,
        current_cpa: float,
        target_cpa: float,
        conversion_count: int,
    ) -> dict:
        """根据实际表现建议调价"""
        if conversion_count < 10:
            return {
                "action": "hold",
                "adjustment": 0,
                "reason": f"转化量不足({conversion_count})，建议继续观察，至少累计20个转化再调价",
            }

        ratio = current_cpa / target_cpa

        if ratio > 1.5:
            return {
                "action": "decrease",
                "adjustment": -0.25,
                "reason": f"CPA ¥{current_cpa:.1f} 超出目标{ratio:.0%}，建议降价25%",
            }
        elif ratio > 1.2:
            return {
                "action": "decrease",
                "adjustment": -0.15,
                "reason": f"CPA ¥{current_cpa:.1f} 略超目标，建议降价15%",
            }
        elif ratio < 0.7:
            return {
                "action": "increase",
                "adjustment": 0.20,
                "reason": f"CPA ¥{current_cpa:.1f} 低于目标，可以加价20%放量",
            }
        elif ratio < 0.85:
            return {
                "action": "increase",
                "adjustment": 0.10,
                "reason": f"CPA ¥{current_cpa:.1f} 偏低，建议加价10%获取更多流量",
            }
        else:
            return {
                "action": "hold",
                "adjustment": 0,
                "reason": f"CPA ¥{current_cpa:.1f} 在目标范围内，保持当前出价",
            }
