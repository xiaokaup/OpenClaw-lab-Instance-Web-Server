"""
渠道选择引擎 — 智能选择投放渠道 + 预算分配

核心功能:
- 基于内容特征 + 目标人群自动推荐渠道组合
- 预算智能分配 (按渠道ROI历史 + 人群匹配度)
- A/B对照组设计

渠道评估维度:
1. 人群匹配度: 目标受众在该渠道的浓度
2. 内容适配度: 内容形态是否适合该渠道
3. 历史ROI: 该渠道类似内容的投放效果
4. 成本效率: CPC/CPM 区间
5. 规模潜力: 渠道日活/覆盖量
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ChannelAllocation:
    """单渠道预算分配"""
    channel: str               # douyin, xiaohongshu, etc.
    channel_name: str          # 中文名
    budget: float              # 预算金额 (元)
    budget_pct: float          # 预算占比
    daily_impression_est: int  # 预估日曝光
    daily_click_est: int       # 预估日点击
    estimated_cpc: float       # 预估CPC (元)
    estimated_ctr: float       # 预估CTR
    roi_score: float           # 历史ROI评分 (0-10)
    audience_match: float      # 人群匹配度 (0-100)
    bid_recommendation: str    # 出价建议 e.g. "OCPM ¥80/千次展示"
    targeting: dict = field(default_factory=dict)  # 定向参数
    notes: list[str] = field(default_factory=list)


@dataclass
class ChannelPlan:
    """渠道投放方案"""
    total_budget: float
    daily_budget: float
    channels: list[ChannelAllocation]
    ab_test_groups: list[dict] = field(default_factory=list)  # A/B对照组
    summary: str = ""
    risk_notes: list[str] = field(default_factory=list)


# ── 渠道数据 (2026年基准) ──────────────────────────────────

CHANNEL_PROFILES: dict[str, dict] = {
    "douyin": {
        "name": "抖音",
        "type": "short_video",
        "dau": 800_000_000,       # 8亿DAU
        "avg_cpc": (0.5, 3.0),     # CPC范围(元)
        "avg_cpm": (20, 80),       # CPM范围(元)
        "avg_ctr": (1.5, 5.0),     # CTR范围(%)
        "best_content": ["短剧", "知识科普", "人格测试", "情感共鸣"],
        "best_audience": ["18-35岁", "女性偏多", "下沉+一线"],
        "ad_types": ["信息流", "DOU+", "巨量引擎"],
        "roi_benchmark": 2.5,      # 行业平均ROI
        "bid_modes": ["OCPM", "CPC", "CPM"],
    },
    "xiaohongshu": {
        "name": "小红书",
        "type": "social_notes",
        "dau": 350_000_000,
        "avg_cpc": (0.3, 2.0),
        "avg_cpm": (15, 50),
        "avg_ctr": (2.0, 6.0),
        "best_content": ["种草笔记", "经验分享", "心理成长", "生活方式"],
        "best_audience": ["18-35岁", "女性为主(70%)", "一二线城市"],
        "ad_types": ["信息流", "搜索广告"],
        "roi_benchmark": 3.0,
        "bid_modes": ["OCPM", "CPC"],
    },
    "bilibili": {
        "name": "B站",
        "type": "mid_video",
        "dau": 120_000_000,
        "avg_cpc": (0.8, 4.0),
        "avg_cpm": (25, 100),
        "avg_ctr": (1.0, 3.0),
        "best_content": ["深度分析", "知识科普", "测评", "心理剖析"],
        "best_audience": ["16-30岁", "男性偏多", "学生+白领"],
        "ad_types": ["信息流", "UP主商单", "品牌专区"],
        "roi_benchmark": 2.0,
        "bid_modes": ["CPM", "CPC"],
    },
    "zhihu": {
        "name": "知乎",
        "type": "text_qa",
        "dau": 45_000_000,
        "avg_cpc": (1.0, 5.0),
        "avg_cpm": (20, 60),
        "avg_ctr": (0.5, 2.0),
        "best_content": ["深度回答", "专业分析", "数据科普", "理性讨论"],
        "best_audience": ["22-40岁", "男性偏多", "高学历", "一二线"],
        "ad_types": ["信息流", "知+", "品牌提问"],
        "roi_benchmark": 2.5,
        "bid_modes": ["CPC", "OCPC"],
    },
    "wechat_moments": {
        "name": "微信朋友圈",
        "type": "social_feed",
        "dau": 900_000_000,
        "avg_cpc": (1.0, 5.0),
        "avg_cpm": (30, 120),
        "avg_ctr": (0.3, 1.5),
        "best_content": ["社交话题", "测试", "互动", "轻娱乐"],
        "best_audience": ["全年龄", "全地域", "熟人社交"],
        "ad_types": ["朋友圈广告", "公众号广告", "视频号广告"],
        "roi_benchmark": 2.0,
        "bid_modes": ["OCPM", "CPM", "CPC"],
    },
    "weibo": {
        "name": "微博",
        "type": "micro_blog",
        "dau": 280_000_000,
        "avg_cpc": (0.3, 1.5),
        "avg_cpm": (10, 40),
        "avg_ctr": (0.5, 2.5),
        "best_content": ["热点话题", "争议讨论", "娱乐八卦", "轻测试"],
        "best_audience": ["18-35岁", "女性偏多", "追热点人群"],
        "ad_types": ["粉丝通", "话题广告", "搜索广告"],
        "roi_benchmark": 1.8,
        "bid_modes": ["CPM", "CPE"],
    },
}


class ChannelSelector:
    """
    渠道选择引擎

    用法:
        selector = ChannelSelector()
        plan = selector.select(
            content={"topic": "人格测试", "type": "quiz", "formats": ["短视频", "图文"]},
            target_audience={"age": "18-35", "interests": ["心理", "自我提升"]},
            budget_daily=500,
        )
    """

    def select(
        self,
        content: dict,
        target_audience: dict,
        budget_daily: float = 500,
        max_channels: int = 4,
        min_budget_per_channel: float = 50,
        historical_roi: Optional[dict] = None,
    ) -> ChannelPlan:
        """
        选择渠道组合 + 分配预算

        Args:
            content: {"topic", "type", "formats", "cta", "length"}
            target_audience: {"age", "gender", "cities", "interests", "education"}
            budget_daily: 日预算(元)
            max_channels: 最多投放渠道数
            min_budget_per_channel: 单渠道最低预算
            historical_roi: 各渠道历史ROI数据(可选)

        Returns:
            ChannelPlan
        """
        # 1. 为每个渠道打分
        scored = []
        for ch_key, profile in CHANNEL_PROFILES.items():
            score = self._score_channel(ch_key, profile, content, target_audience, historical_roi)
            if score > 0:
                scored.append((ch_key, profile, score))

        # 2. 按分数排序，取Top N
        scored.sort(key=lambda x: x[2], reverse=True)
        selected = scored[:max_channels]

        if not selected:
            return ChannelPlan(
                total_budget=budget_daily * 30,
                daily_budget=budget_daily,
                channels=[],
                risk_notes=["未找到匹配的渠道"],
            )

        # 3. 按分数比例分配预算
        total_score = sum(s[2] for s in selected)
        allocations = []

        for ch_key, profile, score in selected:
            pct = score / total_score
            budget = round(budget_daily * pct, 2)

            # 确保不低于最低预算
            if budget < min_budget_per_channel:
                budget = min_budget_per_channel

            # 估算曝光和点击
            avg_cpm = (profile["avg_cpm"][0] + profile["avg_cpm"][1]) / 2
            avg_ctr = (profile["avg_ctr"][0] + profile["avg_ctr"][1]) / 2 / 100
            avg_cpc = (profile["avg_cpc"][0] + profile["avg_cpc"][1]) / 2

            impressions_est = int((budget / avg_cpm) * 1000) if avg_cpm > 0 else 0
            clicks_est = int(impressions_est * avg_ctr)

            # 出价建议
            bid_rec = self._bid_recommendation(profile, content)

            # 定向参数
            targeting = self._build_targeting(target_audience, ch_key)

            allocations.append(ChannelAllocation(
                channel=ch_key,
                channel_name=profile["name"],
                budget=budget,
                budget_pct=round(pct * 100, 1),
                daily_impression_est=impressions_est,
                daily_click_est=clicks_est,
                estimated_cpc=round(avg_cpc, 2),
                estimated_ctr=round(avg_ctr * 100, 2),
                roi_score=round(min(10, profile["roi_benchmark"] * 2.5), 1),
                audience_match=round(min(100, score * 20), 0),
                bid_recommendation=bid_rec,
                targeting=targeting,
                notes=[],
            ))

        # 4. 重新归一化预算(确保总额等于budget_daily)
        total_allocated = sum(a.budget for a in allocations)
        if total_allocated > 0:
            factor = budget_daily / total_allocated
            for a in allocations:
                a.budget = round(a.budget * factor, 2)
                a.budget_pct = round(a.budget / budget_daily * 100, 1)

        # 5. 生成A/B对照组建议
        ab_groups = self._design_ab_test(allocations, content)

        # 6. 生成总结
        summary = self._generate_summary(allocations, content, budget_daily)

        # 7. 风险评估
        risks = self._assess_risks(allocations, content, budget_daily)

        return ChannelPlan(
            total_budget=round(budget_daily * 30, 2),
            daily_budget=budget_daily,
            channels=allocations,
            ab_test_groups=ab_groups,
            summary=summary,
            risk_notes=risks,
        )

    def _score_channel(
        self,
        ch_key: str,
        profile: dict,
        content: dict,
        audience: dict,
        historical_roi: Optional[dict],
    ) -> float:
        """综合打分 (0-5分制)"""
        score = 0.0

        # 1. 内容适配度 (权重 30%)
        content_type = content.get("type", "")
        formats = content.get("formats", [])
        topic = content.get("topic", "")

        if content_type == "quiz" and ch_key in ["douyin", "xiaohongshu", "wechat_moments"]:
            score += 1.5  # 测试类天然适合这些渠道
        elif content_type == "article" and ch_key in ["zhihu", "bilibili", "wechat_mp"]:
            score += 1.5

        if "短视频" in formats and ch_key in ["douyin", "bilibili"]:
            score += 0.5
        if "图文" in formats and ch_key in ["xiaohongshu", "weibo", "zhihu"]:
            score += 0.5

        # 2. 人群匹配度 (权重 40%)
        audience_age = audience.get("age", "")
        if "18-35" in str(audience_age) and ch_key in profile.get("best_audience", [])[0]:
            score += 2.0
        if audience.get("interests"):
            for interest in audience["interests"]:
                if interest in str(profile.get("best_content", [])):
                    score += 0.3

        # 3. 历史ROI (权重 20%)
        if historical_roi and ch_key in historical_roi:
            roi = historical_roi[ch_key]
            if roi > 3:
                score += 1.0
            elif roi > 2:
                score += 0.7
            elif roi > 1:
                score += 0.3
        else:
            score += profile["roi_benchmark"] / 5  # 用行业基准

        # 4. 规模潜力 (权重 10%)
        dau = profile["dau"]
        if dau > 500_000_000:
            score += 0.5
        elif dau > 100_000_000:
            score += 0.3

        return round(score, 2)

    def _bid_recommendation(self, profile: dict, content: dict) -> str:
        """生成出价建议"""
        bid_modes = profile.get("bid_modes", ["OCPM"])
        mode = "OCPM" if "OCPM" in bid_modes else bid_modes[0]
        avg_cpm = (profile["avg_cpm"][0] + profile["avg_cpm"][1]) / 2

        if content.get("goal") == "conversion":
            return f"{mode} ¥{int(avg_cpm * 0.8)}/千次展示 (优化转化)"
        elif content.get("goal") == "traffic":
            return f"CPC ¥{profile['avg_cpc'][0]}起"
        return f"{mode} ¥{int(avg_cpm)}/千次展示"

    def _build_targeting(self, audience: dict, channel: str) -> dict:
        """构建渠道定向参数"""
        targeting = {}

        age = audience.get("age", "")
        if age:
            # 渠道特定的年龄格式
            if channel in ["douyin", "oceanengine"]:
                # 巨量: AGE_BETWEEN_18_23, etc.
                targeting["age"] = self._map_age_oceanengine(age)
            elif channel == "wechat_moments":
                targeting["age"] = [age.replace("岁", "").replace("-", "~")]

        gender = audience.get("gender", "")
        if gender:
            if channel in ["douyin", "oceanengine"]:
                mapping = {"男": "GENDER_MALE", "女": "GENDER_FEMALE"}
                targeting["gender"] = mapping.get(gender, "")

        interests = audience.get("interests", [])
        if interests:
            targeting["interests"] = interests

        return targeting

    def _map_age_oceanengine(self, age_str: str) -> list[str]:
        """将年龄范围映射到巨量引擎年龄定向"""
        mapping = {
            "18-35": ["AGE_BETWEEN_18_23", "AGE_BETWEEN_24_30", "AGE_BETWEEN_31_35"],
            "18-24": ["AGE_BETWEEN_18_23"],
            "25-35": ["AGE_BETWEEN_24_30", "AGE_BETWEEN_31_35"],
            "18-23": ["AGE_BETWEEN_18_23"],
            "24-30": ["AGE_BETWEEN_24_30"],
            "31-40": ["AGE_BETWEEN_31_35", "AGE_BETWEEN_36_40"],
        }
        return mapping.get(age_str, [])

    def _design_ab_test(
        self,
        allocations: list[ChannelAllocation],
        content: dict,
    ) -> list[dict]:
        """设计A/B对照组"""
        if len(allocations) < 2:
            return []

        # 选预算最高的2个渠道做A/B
        sorted_alloc = sorted(allocations, key=lambda a: a.budget, reverse=True)
        primary = sorted_alloc[0]

        ab_groups = [
            {
                "name": f"A组-{primary.channel_name}",
                "channel": primary.channel,
                "budget": round(primary.budget * 0.7, 2),
                "variant": "主素材",
                "metric": "点击率",
                "hypothesis": "原始素材 vs 优化素材的CTR对比",
            },
            {
                "name": f"B组-{primary.channel_name}",
                "channel": primary.channel,
                "budget": round(primary.budget * 0.3, 2),
                "variant": "变体素材",
                "metric": "点击率",
                "hypothesis": "标题中加入数字 vs 不加数字的CTR对比",
            },
        ]

        return ab_groups

    def _generate_summary(
        self,
        allocations: list[ChannelAllocation],
        content: dict,
        budget: float,
    ) -> str:
        """生成方案摘要"""
        total_impressions = sum(a.daily_impression_est for a in allocations)
        total_clicks = sum(a.daily_click_est for a in allocations)
        avg_cpc = sum(a.estimated_cpc * a.budget for a in allocations) / max(budget, 1)

        parts = [
            f"日预算 ¥{budget}/天",
            f"覆盖 {len(allocations)} 个渠道",
            f"预估日曝光 {total_impressions:,} 次",
            f"预估日点击 {total_clicks:,} 次",
            f"加权平均CPC ¥{avg_cpc:.2f}",
        ]

        # 主渠道
        if allocations:
            primary = max(allocations, key=lambda a: a.budget)
            parts.append(f"主投渠道: {primary.channel_name} ({primary.budget_pct}%)")

        return " · ".join(parts)

    def _assess_risks(
        self,
        allocations: list[ChannelAllocation],
        content: dict,
        budget: float,
    ) -> list[str]:
        """风险评估"""
        risks = []

        if budget < 100:
            risks.append("预算过低(¥{:.0f}/天)，单渠道数据难以统计显著，建议至少¥300/天".format(budget))

        if len(allocations) == 0:
            risks.append("无可用渠道，检查内容和目标人群设置")
        elif len(allocations) >= 4:
            risks.append("渠道过多(≥4个)可能导致预算分散，建议从2-3个渠道开始测试")

        # 检查是否有单一渠道占比过高
        if allocations:
            primary = max(allocations, key=lambda a: a.budget)
            if primary.budget_pct > 60:
                risks.append(f"{primary.channel_name} 占比{primary.budget_pct}%，建议控制在50%以内分散风险")

        return risks

    def get_channel_profiles(self) -> dict:
        """获取所有渠道信息 (供前端展示)"""
        return {
            key: {
                "key": key,
                "name": p["name"],
                "type": p["type"],
                "dau": p["dau"],
                "avg_cpc": p["avg_cpc"],
                "avg_cpm": p["avg_cpm"],
                "best_content": p["best_content"],
                "best_audience": p["best_audience"],
                "roi_benchmark": p["roi_benchmark"],
                "bid_modes": p["bid_modes"],
            }
            for key, p in CHANNEL_PROFILES.items()
        }
