"""
ROI实时监控引擎 — 投放效果追踪 + 异常预警

核心功能:
- 多维度ROI计算 (渠道/计划/素材)
- 实时CPA监控
- 异常熔断机制
- 趋势预测

监控指标:
- ROI (投入产出比)
- CPA (单次转化成本)
- CTR (点击率)  
- CVR (转化率)
- 消耗速度 (预算消耗率)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional


class AlertLevel(str, Enum):
    OK = "ok"           # 正常
    WATCH = "watch"     # 关注 (接近阈值)
    WARN = "warn"       # 警告 (超出阈值)
    CRITICAL = "critical"  # 严重 (需要立即介入)
    MELTDOWN = "meltdown"  # 熔断 (自动暂停)


@dataclass
class ROISnapshot:
    """ROI快照 (单时间点)"""
    timestamp: str              # ISO时间
    channel: str
    campaign_id: str = ""
    # 核心指标
    spend: float = 0.0          # 花费(元)
    revenue: float = 0.0        # 收入(元)
    roi: float = 0.0            # ROI
    impressions: int = 0        # 曝光
    clicks: int = 0             # 点击
    conversions: int = 0        # 转化
    # 衍生指标
    ctr: float = 0.0            # 点击率
    cvr: float = 0.0            # 转化率
    cpc: float = 0.0            # 点击成本
    cpa: float = 0.0            # 转化成本
    cpm: float = 0.0            # 千次展示成本
    # 预算
    daily_budget: float = 0.0   # 日预算
    spend_rate: float = 0.0     # 预算消耗率 (0-1)
    # 状态
    alert_level: AlertLevel = AlertLevel.OK
    alert_message: str = ""


@dataclass
class ChannelROI:
    """渠道级ROI汇总"""
    channel: str
    channel_name: str
    total_spend: float
    total_revenue: float
    roi: float
    total_impressions: int
    total_clicks: int
    total_conversions: int
    avg_cpa: float
    avg_ctr: float
    avg_cvr: float
    trend: str                # up | down | stable
    alert_level: AlertLevel
    campaigns: list[dict] = field(default_factory=list)


class ROIMonitor:
    """
    ROI实时监控

    用法:
        monitor = ROIMonitor(target_roi=2.0, target_cpa=30.0, daily_budget=500)
        snapshot = monitor.record(
            channel="douyin",
            campaign_id="mock-123",
            spend=45.0, revenue=120.0, impressions=5000, clicks=150, conversions=4,
        )
        alert = monitor.check_alert("douyin", snapshot)
    """

    def __init__(
        self,
        target_roi: float = 2.0,
        target_cpa: float = 30.0,
        daily_budget: float = 500.0,
        max_cpa_multiplier: float = 2.0,   # CPA超过目标N倍触发熔断
        min_roi_threshold: float = 0.5,     # ROI低于N触发警告
    ):
        self.target_roi = target_roi
        self.target_cpa = target_cpa
        self.daily_budget = daily_budget
        self.max_cpa_multiplier = max_cpa_multiplier
        self.min_roi_threshold = min_roi_threshold

        # 存储历史快照
        self._history: dict[str, list[ROISnapshot]] = {}

    def record(
        self,
        channel: str,
        campaign_id: str = "",
        spend: float = 0.0,
        revenue: float = 0.0,
        impressions: int = 0,
        clicks: int = 0,
        conversions: int = 0,
    ) -> ROISnapshot:
        """记录一次ROI快照"""
        # 计算衍生指标
        roi = revenue / spend if spend > 0 else 0.0
        ctr = clicks / impressions if impressions > 0 else 0.0
        cvr = conversions / clicks if clicks > 0 else 0.0
        cpc = spend / clicks if clicks > 0 else 0.0
        cpa = spend / conversions if conversions > 0 else 0.0
        cpm = spend / impressions * 1000 if impressions > 0 else 0.0
        spend_rate = spend / self.daily_budget if self.daily_budget > 0 else 0.0

        snapshot = ROISnapshot(
            timestamp=datetime.now().isoformat(),
            channel=channel,
            campaign_id=campaign_id,
            spend=round(spend, 2),
            revenue=round(revenue, 2),
            roi=round(roi, 2),
            impressions=impressions,
            clicks=clicks,
            conversions=conversions,
            ctr=round(ctr, 4),
            cvr=round(cvr, 4),
            cpc=round(cpc, 2),
            cpa=round(cpa, 2),
            cpm=round(cpm, 2),
            daily_budget=self.daily_budget,
            spend_rate=round(spend_rate, 4),
        )

        # 评估告警级别
        snapshot.alert_level, snapshot.alert_message = self._evaluate_alert(snapshot)

        # 存储历史
        key = f"{channel}:{campaign_id}" if campaign_id else channel
        if key not in self._history:
            self._history[key] = []
        self._history[key].append(snapshot)

        # 保留最近1000条
        if len(self._history[key]) > 1000:
            self._history[key] = self._history[key][-1000:]

        return snapshot

    def _evaluate_alert(self, s: ROISnapshot) -> tuple[AlertLevel, str]:
        """评估告警级别"""
        messages = []
        max_level = AlertLevel.OK

        # 1. CPA检查
        if s.cpa > 0 and s.conversions >= 5:
            cpa_ratio = s.cpa / self.target_cpa
            if cpa_ratio > self.max_cpa_multiplier:
                max_level = AlertLevel.MELTDOWN
                messages.append(f"🔥 CPA ¥{s.cpa:.1f} 超过目标{int(cpa_ratio*100)}%，触发熔断!")
            elif cpa_ratio > 1.5:
                if max_level.value < AlertLevel.CRITICAL.value:
                    max_level = AlertLevel.CRITICAL
                messages.append(f"🚨 CPA ¥{s.cpa:.1f} 严重超标")
            elif cpa_ratio > 1.2:
                if max_level.value < AlertLevel.WARN.value:
                    max_level = AlertLevel.WARN
                messages.append(f"⚠️ CPA ¥{s.cpa:.1f} 超标20%")

        # 2. ROI检查
        if s.roi > 0 and s.spend > 50:  # 花费>50元才开始判断
            if s.roi < self.min_roi_threshold:
                if max_level.value < AlertLevel.CRITICAL.value:
                    max_level = AlertLevel.CRITICAL
                messages.append(f"📉 ROI {s.roi:.1f} 低于最低阈值{self.min_roi_threshold}")
            elif s.roi < self.target_roi * 0.7:
                if max_level.value < AlertLevel.WARN.value:
                    max_level = AlertLevel.WARN
                messages.append(f"📊 ROI {s.roi:.1f} 低于目标70%")

        # 3. 预算消耗速度
        if s.spend_rate > 0.9 and s.conversions == 0:
            if max_level.value < AlertLevel.WARN.value:
                max_level = AlertLevel.WARN
            messages.append(f"💰 预算将耗尽({s.spend_rate:.0%})但无转化")

        # 4. CTR异常低
        if s.impressions > 1000 and s.ctr < 0.005:
            if max_level.value < AlertLevel.WATCH.value:
                max_level = AlertLevel.WATCH
            messages.append(f"👀 CTR {s.ctr:.2%} 偏低，建议更换素材")

        if not messages:
            messages.append("✅ 指标正常")

        return max_level, " · ".join(messages)

    def check_alert(self, channel: str, campaign_id: str = "") -> dict:
        """检查最新告警状态"""
        key = f"{channel}:{campaign_id}" if campaign_id else channel
        history = self._history.get(key, [])
        if not history:
            return {"level": AlertLevel.OK, "message": "暂无数据"}

        latest = history[-1]
        return {"level": latest.alert_level, "message": latest.alert_message}

    def get_channel_summary(
        self,
        channel: str,
        channel_name: str = "",
        lookback_hours: int = 24,
    ) -> ChannelROI:
        """获取渠道汇总数据"""
        total_spend = 0.0
        total_revenue = 0.0
        total_impressions = 0
        total_clicks = 0
        total_conversions = 0
        max_alert = AlertLevel.OK

        cutoff = datetime.now() - timedelta(hours=lookback_hours)
        campaign_data: dict[str, dict] = {}

        for key, snapshots in self._history.items():
            if not key.startswith(f"{channel}:"):
                continue
            cid = key.split(":", 1)[1] if ":" in key else ""

            for s in snapshots:
                if datetime.fromisoformat(s.timestamp) < cutoff:
                    continue
                total_spend += s.spend
                total_revenue += s.revenue
                total_impressions += s.impressions
                total_clicks += s.clicks
                total_conversions += s.conversions
                if s.alert_level.value > max_alert.value:
                    max_alert = s.alert_level

                if cid:
                    if cid not in campaign_data:
                        campaign_data[cid] = {"spend": 0, "revenue": 0, "conversions": 0}
                    campaign_data[cid]["spend"] += s.spend
                    campaign_data[cid]["revenue"] += s.revenue
                    campaign_data[cid]["conversions"] += s.conversions

        roi = total_revenue / total_spend if total_spend > 0 else 0.0
        avg_ctr = total_clicks / total_impressions if total_impressions > 0 else 0.0
        avg_cvr = total_conversions / total_clicks if total_clicks > 0 else 0.0
        avg_cpa = total_spend / total_conversions if total_conversions > 0 else 0.0

        # 判断趋势
        trend = self._detect_trend(channel)

        campaigns = [
            {
                "campaign_id": cid,
                "spend": round(d["spend"], 2),
                "revenue": round(d["revenue"], 2),
                "roi": round(d["revenue"] / d["spend"], 2) if d["spend"] > 0 else 0,
                "conversions": d["conversions"],
            }
            for cid, d in campaign_data.items()
        ]

        return ChannelROI(
            channel=channel,
            channel_name=channel_name,
            total_spend=round(total_spend, 2),
            total_revenue=round(total_revenue, 2),
            roi=round(roi, 2),
            total_impressions=total_impressions,
            total_clicks=total_clicks,
            total_conversions=total_conversions,
            avg_cpa=round(avg_cpa, 2),
            avg_ctr=round(avg_ctr, 4),
            avg_cvr=round(avg_cvr, 4),
            trend=trend,
            alert_level=max_alert,
            campaigns=campaigns,
        )

    def _detect_trend(self, channel: str) -> str:
        """检测ROI趋势 (基于最近6次快照)"""
        snapshots = []
        for key, history in self._history.items():
            if key.startswith(f"{channel}:"):
                snapshots.extend(history)

        if len(snapshots) < 3:
            return "stable"

        # 取最近6次
        recent = sorted(snapshots, key=lambda s: s.timestamp)[-6:]
        roi_values = [s.roi for s in recent if s.roi > 0]

        if len(roi_values) < 3:
            return "stable"

        first_half = roi_values[:len(roi_values)//2]
        second_half = roi_values[len(roi_values)//2:]

        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)

        change = (avg_second - avg_first) / max(avg_first, 0.01)
        if change > 0.1:
            return "up"
        elif change < -0.1:
            return "down"
        return "stable"

    def get_all_summaries(self, channel_names: Optional[dict[str, str]] = None) -> list[ChannelROI]:
        """获取所有渠道汇总"""
        channels = set()
        for key in self._history:
            ch = key.split(":")[0]
            channels.add(ch)

        names = channel_names or {}
        return [
            self.get_channel_summary(ch, names.get(ch, ch))
            for ch in sorted(channels)
        ]

    def should_pause(self, channel: str) -> tuple[bool, str]:
        """判断是否应该暂停某渠道投放"""
        alert = self.check_alert(channel)
        if alert["level"] in (AlertLevel.MELTDOWN, AlertLevel.CRITICAL):
            return True, f"告警级别 {alert['level']}: {alert['message']}"
        return False, ""

    def get_meltdown_protection_rules(self) -> list[dict]:
        """获取熔断保护规则"""
        return [
            {
                "rule": "CPA熔断",
                "condition": f"连续2小时 CPA > ¥{self.target_cpa * self.max_cpa_multiplier:.0f} 且 转化≥5",
                "action": "自动暂停计划 + 通知投投",
            },
            {
                "rule": "预算耗尽保护",
                "condition": f"预算消耗≥95% 且 ROI < 1.0",
                "action": "停止当日投放，次日恢复",
            },
            {
                "rule": "空耗保护",
                "condition": "花费≥¥50 且 0转化",
                "action": "暂停计划，检查转化追踪配置",
            },
            {
                "rule": "CTR衰减预警",
                "condition": "CTR连续2天下降且降幅>30%",
                "action": "标记素材衰减，建议替换",
            },
        ]
