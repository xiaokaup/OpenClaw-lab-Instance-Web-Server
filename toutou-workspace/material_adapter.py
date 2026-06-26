"""
素材适配引擎 — 1份内容 → 多平台规格

核心功能:
- 根据源素材自动生成各平台适配版本
- 管理各平台素材规格约束
- 内容裁剪/缩放/文字适配

平台规格参考 (2026):
┌──────────┬──────────┬──────────┬──────────┬──────────┐
│ 平台     │ 封面比例  │ 标题字数  │ 描述字数  │ CTA限制  │
├──────────┼──────────┼──────────┼──────────┼──────────┤
│ 抖音     │ 9:16     │ 5-30字   │ 无       │ 8字内    │
│ 小红书   │ 3:4      │ ≤20字    │ ≤1000字  │ 无       │
│ B站      │ 16:9     │ ≤80字    │ ≤250字   │ 无       │
│ 朋友圈    │ 1:1      │ ≤30字    │ ≤40字    │ 4字内    │
│ 公众号    │ 2.35:1   │ ≤64字    │ ≤140字   │ 无       │
│ 知乎      │ 16:9     │ ≤30字    │ ≤150字   │ 无       │
│ 微博      │ 16:9     │ ≤32字    │ ≤140字   │ 无       │
└──────────┴──────────┴──────────┴──────────┴──────────┘
"""

from dataclasses import dataclass, field
from typing import Optional
import re


@dataclass
class PlatformSpec:
    """单个平台的素材规格约束"""
    platform: str               # douyin, xiaohongshu, bilibili, wechat_moments, wechat_mp, zhihu, weibo
    platform_name: str          # 中文名
    aspect_ratio: str           # 封面比例 e.g. "9:16", "3:4"
    aspect_w: int
    aspect_h: int
    title_max_chars: int        # 标题最大字数
    title_min_chars: int = 3    # 标题最小字数
    desc_max_chars: int = 0     # 描述最大字数 (0=无限制)
    cta_max_chars: int = 0      # CTA最大字数 (0=无限制)
    supports_video: bool = True
    supports_image: bool = True
    supports_carousel: bool = False   # 轮播/多图
    supports_long_text: bool = False  # 长文支持 (知乎/公众号)

    def validate_title(self, title: str) -> tuple[bool, str]:
        """校验标题是否符合平台规格"""
        length = len(title)
        if length < self.title_min_chars:
            return False, f"标题过短（{length}字，最少{self.title_min_chars}字）"
        if length > self.title_max_chars:
            return False, f"标题过长（{length}字，最长{self.title_max_chars}字）"
        return True, "OK"


# ── 平台规格注册表 ──────────────────────────────────────────

PLATFORM_SPECS: dict[str, PlatformSpec] = {
    "douyin": PlatformSpec(
        platform="douyin", platform_name="抖音",
        aspect_ratio="9:16", aspect_w=9, aspect_h=16,
        title_max_chars=30, title_min_chars=5,
        desc_max_chars=0, cta_max_chars=8,
        supports_carousel=False,
    ),
    "xiaohongshu": PlatformSpec(
        platform="xiaohongshu", platform_name="小红书",
        aspect_ratio="3:4", aspect_w=3, aspect_h=4,
        title_max_chars=20, title_min_chars=3,
        desc_max_chars=1000, cta_max_chars=0,
        supports_video=True, supports_image=True,
    ),
    "bilibili": PlatformSpec(
        platform="bilibili", platform_name="B站",
        aspect_ratio="16:9", aspect_w=16, aspect_h=9,
        title_max_chars=80, title_min_chars=5,
        desc_max_chars=250, cta_max_chars=0,
    ),
    "wechat_moments": PlatformSpec(
        platform="wechat_moments", platform_name="微信朋友圈",
        aspect_ratio="1:1", aspect_w=1, aspect_h=1,
        title_max_chars=30, title_min_chars=3,
        desc_max_chars=40, cta_max_chars=4,
        supports_carousel=True,
    ),
    "wechat_mp": PlatformSpec(
        platform="wechat_mp", platform_name="微信公众号",
        aspect_ratio="2.35:1", aspect_w=47, aspect_h=20,
        title_max_chars=64, title_min_chars=3,
        desc_max_chars=140, cta_max_chars=0,
        supports_long_text=True,
    ),
    "zhihu": PlatformSpec(
        platform="zhihu", platform_name="知乎",
        aspect_ratio="16:9", aspect_w=16, aspect_h=9,
        title_max_chars=30, title_min_chars=3,
        desc_max_chars=150, cta_max_chars=0,
        supports_long_text=True,
    ),
    "weibo": PlatformSpec(
        platform="weibo", platform_name="微博",
        aspect_ratio="16:9", aspect_w=16, aspect_h=9,
        title_max_chars=32, title_min_chars=3,
        desc_max_chars=140, cta_max_chars=0,
        supports_carousel=True,
    ),
    # ── 广告投放平台 ──
    "oceanengine": PlatformSpec(
        platform="oceanengine", platform_name="巨量引擎(抖音广告)",
        aspect_ratio="9:16", aspect_w=9, aspect_h=16,
        title_max_chars=30, title_min_chars=5,
        desc_max_chars=0, cta_max_chars=8,
    ),
    "wechat_ads": PlatformSpec(
        platform="wechat_ads", platform_name="微信广告",
        aspect_ratio="1:1", aspect_w=1, aspect_h=1,
        title_max_chars=30, title_min_chars=3,
        desc_max_chars=40, cta_max_chars=4,
        supports_carousel=True,
    ),
}


# ── 内容裁剪策略 ────────────────────────────────────────────

@dataclass
class AdaptedMaterial:
    """适配后的单平台素材"""
    platform: str
    platform_name: str
    title: str
    description: str
    cta: str
    aspect_ratio: str
    # 视觉建议
    visual_note: str           # 设计建议
    color_suggestion: str      # 配色建议
    # 原始信息保留
    source_title: str = ""
    # 额外信息
    hashtags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class MaterialAdapter:
    """
    素材适配引擎

    输入: 一份"源内容" (标题+正文+CTA+目标人群)
    输出: N份平台适配素材

    用法:
        adapter = MaterialAdapter()
        source = {
            "title": "你的人格画像值多少钱？",
            "body": "...核心内容...",
            "cta": "免费测试",
            "target_audience": "18-35岁社媒用户",
        }
        materials = adapter.adapt(source, platforms=["douyin", "xiaohongshu", "wechat_moments"])
    """

    # 平台语气映射
    PLATFORM_TONE: dict[str, dict] = {
        "douyin": {
            "style": "快节奏·悬念感·情绪钩子",
            "prefix_templates": [
                "🔥 {title}",
                "你敢信？{title}",
                "{title}，结果我哭了",
            ],
        },
        "xiaohongshu": {
            "style": "种草感·经验分享·精致排版",
            "prefix_templates": [
                "✨ {title} | 亲测有效",
                "姐妹们！{title}",
                "发现一个超准的测试：{title}",
            ],
        },
        "bilibili": {
            "style": "深度·幽默·弹幕友好",
            "prefix_templates": [
                "【深度】{title}",
                "为什么{title}？认真聊聊",
                "{title}，这个测试让我沉默了",
            ],
        },
        "wechat_moments": {
            "style": "社交分享·简洁有力·好奇心驱动",
            "prefix_templates": [
                "{title}",
                "试了一下{title}",
                "朋友推荐的测试：{title}",
            ],
        },
        "zhihu": {
            "style": "专业·分析·数据驱动",
            "prefix_templates": [
                "如何评价{title}？深度分析",
                "{title}：一个AI视角的解读",
            ],
        },
        "weibo": {
            "style": "话题感·争议性·短平快",
            "prefix_templates": [
                "#{title}# 这个话题……",
                "{title}，你觉得呢？",
            ],
        },
    }

    # 平台通用CTAs
    DEFAULT_CTAS: dict[str, str] = {
        "douyin": "立即测试",
        "xiaohongshu": "测测看",
        "bilibili": "来测一下",
        "wechat_moments": "测一测",
        "zhihu": "开始测试",
        "weibo": "参与测试",
        "oceanengine": "免费测",
        "wechat_ads": "测一测",
    }

    # 平台对应的hashtag推荐
    PLATFORM_HASHTAGS: dict[str, list[str]] = {
        "douyin": ["#心理测试", "#人格测试", "#认识自己", "#AI测试"],
        "xiaohongshu": ["#自我探索", "#人格测试", "#心理成长", "#AI工具"],
        "bilibili": ["#心理测试", "#深度解析", "#认识自我", "#AI"],
        "wechat_moments": [],  # 朋友圈不用hashtag
        "zhihu": [],           # 知乎用话题
        "weibo": ["#心理测试#", "#AI人格测试#", "#认识自己#"],
    }

    def adapt(
        self,
        source: dict,
        platforms: Optional[list[str]] = None,
        tone: str = "auto",     # auto | professional | casual | viral
    ) -> list[AdaptedMaterial]:
        """
        适配源素材到指定平台

        Args:
            source: {
                "title": str,      # 核心标题
                "body": str,       # 正文内容
                "cta": str,        # 行动号召
                "target_audience": str, # 目标人群
                "key_points": list[str], # 核心卖点 (可选)
                "visual_style": str,     # 视觉风格描述 (可选)
            }
            platforms: 目标平台列表，默认全部
            tone: 语气偏好

        Returns:
            AdaptedMaterial列表
        """
        if platforms is None:
            platforms = list(PLATFORM_SPECS.keys())

        title = source.get("title", "")
        body = source.get("body", "")
        cta = source.get("cta", "免费测试")
        key_points = source.get("key_points", [])

        results = []
        for plat_key in platforms:
            spec = PLATFORM_SPECS.get(plat_key)
            if not spec:
                continue

            # 1. 裁剪标题
            adapted_title = self._adapt_title(title, spec)

            # 2. 裁剪描述
            adapted_desc = self._adapt_description(body, spec, key_points)

            # 3. 适配CTA
            adapted_cta = self._adapt_cta(cta, plat_key, spec)

            # 4. 视觉建议
            visual_note = self._visual_note(spec, source)

            # 5. Hashtags
            hashtags = self._get_hashtags(plat_key, source)

            results.append(AdaptedMaterial(
                platform=plat_key,
                platform_name=spec.platform_name,
                title=adapted_title,
                description=adapted_desc,
                cta=adapted_cta,
                aspect_ratio=spec.aspect_ratio,
                visual_note=visual_note,
                color_suggestion=self._color_suggestion(source),
                source_title=title,
                hashtags=hashtags,
                notes=[],
            ))

        return results

    def _adapt_title(self, title: str, spec: PlatformSpec) -> str:
        """裁剪/改写标题以适配平台字数限制"""
        if len(title) <= spec.title_max_chars:
            return title

        # 智能截断：尝试在标点处断开
        truncated = title[:spec.title_max_chars - 1]
        # 反向查找最后一个合适的断点
        for sep in ["。", "！", "？", "，", " ", "·", "、"]:
            idx = truncated.rfind(sep)
            if idx > spec.title_min_chars:
                return truncated[:idx + 1]
        return truncated + "…"

    def _adapt_description(
        self,
        body: str,
        spec: PlatformSpec,
        key_points: list[str],
    ) -> str:
        """裁剪描述文案"""
        if spec.desc_max_chars == 0:
            return body

        if len(body) <= spec.desc_max_chars:
            return body

        # 优先级: key_points > 第一段 > 截断
        if key_points:
            desc = " · ".join(key_points[:3])
            if len(desc) <= spec.desc_max_chars:
                return desc

        # 取第一段
        first_para = body.split("\n\n")[0] if "\n\n" in body else body.split("\n")[0]
        if len(first_para) <= spec.desc_max_chars:
            return first_para

        # 截断
        return first_para[:spec.desc_max_chars - 2] + "…"

    def _adapt_cta(self, cta: str, plat_key: str, spec: PlatformSpec) -> str:
        """适配CTA"""
        if cta and len(cta) <= (spec.cta_max_chars or 999):
            return cta
        return self.DEFAULT_CTAS.get(plat_key, "了解更多")

    def _visual_note(self, spec: PlatformSpec, source: dict) -> str:
        """生成视觉设计建议"""
        style = source.get("visual_style", "简洁现代")
        notes = {
            "douyin": f"竖版9:16，强调第一帧的视觉冲击。{style}风格，留出顶部20%安全区给用户名和文案。",
            "xiaohongshu": f"竖版3:4，精致排版。{style}风格，封面文字要大且可读。建议用拼图形式展示'测试前vs测试后'对比。",
            "bilibili": f"横版16:9，封面需要有信息量。{style}风格，建议用'大字标题+测试界面截图'的组合。",
            "wechat_moments": f"正方形1:1适配。{style}风格，朋友圈广告封面不要放太多文字，靠画面吸引点击。",
            "wechat_mp": f"2.35:1超宽封面。{style}风格，左边留白给标题覆盖。",
            "zhihu": f"横版16:9。{style}风格，知乎封面适合'问题式标题+抽象视觉'。",
            "weibo": f"横版16:9。{style}风格，微博适合多图拼接或GIF动图。",
            "oceanengine": f"竖版9:16信息流广告。{style}风格，前3秒必须有钩子，避免品牌logo占据太大面积。",
            "wechat_ads": f"正方形1:1朋友圈广告。{style}风格，外层文案+图片的配合是核心。",
        }
        return notes.get(spec.platform, f"按{spec.aspect_ratio}比例制作")

    def _color_suggestion(self, source: dict) -> str:
        """基于内容主题推荐配色"""
        style = source.get("visual_style", "")
        topic = source.get("title", "")

        # 简单启发式
        if any(w in topic for w in ["人格", "心理", "自我", "性格"]):
            return "深蓝#1a1a2e + 渐变紫#6366f1 → 暖橙点缀，呼应'内省+成长'主题"
        if any(w in topic for w in ["测试", "挑战", "极限"]):
            return "深黑#0a0a0a + 霓虹绿#22c55e，呼应'探索+挑战'主题"
        return "白底#ffffff + 主色#6366f1，简洁信息安全"

    def _get_hashtags(self, plat_key: str, source: dict) -> list[str]:
        """获取推荐hashtag"""
        tags = list(self.PLATFORM_HASHTAGS.get(plat_key, []))
        # 可以基于内容追加自定义tag
        topic = source.get("title", "")
        if topic:
            clean = re.sub(r'[^\w\u4e00-\u9fff]', '', topic)[:8]
            if plat_key == "weibo":
                tags.insert(0, f"#{clean}#")
            elif plat_key != "wechat_moments":
                tags.insert(0, f"#{clean}")
        return tags

    def get_platform_specs(self) -> dict[str, dict]:
        """获取所有平台规格(用于前端展示)"""
        return {
            key: {
                "platform": spec.platform,
                "name": spec.platform_name,
                "aspect_ratio": spec.aspect_ratio,
                "aspect_w": spec.aspect_w,
                "aspect_h": spec.aspect_h,
                "title_max": spec.title_max_chars,
                "title_min": spec.title_min_chars,
                "desc_max": spec.desc_max_chars,
                "cta_max": spec.cta_max_chars,
                "supports_video": spec.supports_video,
                "supports_carousel": spec.supports_carousel,
            }
            for key, spec in PLATFORM_SPECS.items()
        }
