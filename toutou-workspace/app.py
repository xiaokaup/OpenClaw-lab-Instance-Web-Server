"""
投投 工作区 Flask Blueprint

提供 REST API 端点:
- /api/toutou/status          — 工作区状态
- /api/toutou/adapt           — 素材适配
- /api/toutou/channels        — 渠道选择+预算分配
- /api/toutou/bid             — 出价优化
- /api/toutou/roi             — ROI监控
- /api/toutou/platform-specs  — 平台规格查询
- /api/toutou/connection      — API连接状态
"""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime
from flask import Blueprint, jsonify, request, render_template_string

logger = logging.getLogger("toutou.app")

# Ensure toutou-workspace is importable
_toutou_dir = os.path.dirname(os.path.abspath(__file__))
if _toutou_dir not in sys.path:
    sys.path.insert(0, _toutou_dir)

from material_adapter import MaterialAdapter, PLATFORM_SPECS
from channel_selector import ChannelSelector
from bid_optimizer import BidOptimizer
from roi_monitor import ROIMonitor, AlertLevel
from api_bridge import APIBridge

# ── Blueprint ──────────────────────────────────────────────────

toutou_bp = Blueprint("toutou", __name__, url_prefix="/api/toutou")

# ── 引擎实例 (模块级单例) ──────────────────────────────────────

_adapter = MaterialAdapter()
_selector = ChannelSelector()
_optimizer = BidOptimizer()
_monitor = ROIMonitor(target_roi=2.0, target_cpa=30.0, daily_budget=500.0)
_bridge = APIBridge(demo_mode=True)  # 默认Demo模式，凭证就绪后切为False

# 当前投放状态
_current_plan = None
_active_campaigns: dict[str, dict] = {}  # {channel: {campaign_id, budget, status, ...}}


# ══════════════════════════════════════════════════════════════════
#  状态 & 配置
# ══════════════════════════════════════════════════════════════════

@toutou_bp.route("/status")
def get_status():
    """工作区状态总览"""
    return jsonify({
        "name": "投投 · 投放+分发官",
        "emoji": "📤",
        "model": "v4-flash",
        "role": "渠道选择·素材适配·出价优化·ROI实时监控",
        "phase": "Phase 1",
        "demo_mode": _bridge.demo_mode,
        "connection": _bridge.get_connection_status(),
        "active_campaigns": len(_active_campaigns),
        "has_plan": _current_plan is not None,
        "monitor": {
            "target_roi": _monitor.target_roi,
            "target_cpa": _monitor.target_cpa,
            "daily_budget": _monitor.daily_budget,
        },
    })


@toutou_bp.route("/connection")
def get_connection():
    """API连接状态"""
    return jsonify(_bridge.get_connection_status())


# ══════════════════════════════════════════════════════════════════
#  素材适配 API
# ══════════════════════════════════════════════════════════════════

@toutou_bp.route("/adapt", methods=["POST"])
def adapt_material():
    """
    素材适配: 1份内容 → 多平台规格
    
    Request:
        {
            "title": "你的人格画像值多少钱？",
            "body": "核心内容...",
            "cta": "免费测试",
            "target_audience": "18-35岁社媒用户",
            "key_points": ["AI分析8维度", "3分钟完成", "免费"],
            "platforms": ["douyin", "xiaohongshu", "bilibili", "wechat_moments"]
        }
    """
    data = request.get_json() or {}
    source = {
        "title": data.get("title", ""),
        "body": data.get("body", ""),
        "cta": data.get("cta", "免费测试"),
        "target_audience": data.get("target_audience", ""),
        "key_points": data.get("key_points", []),
        "visual_style": data.get("visual_style", ""),
    }
    platforms = data.get("platforms")  # None = all

    materials = _adapter.adapt(source, platforms)

    return jsonify({
        "source": source,
        "materials": [
            {
                "platform": m.platform,
                "platform_name": m.platform_name,
                "title": m.title,
                "description": m.description,
                "cta": m.cta,
                "aspect_ratio": m.aspect_ratio,
                "visual_note": m.visual_note,
                "color_suggestion": m.color_suggestion,
                "hashtags": m.hashtags,
                "notes": m.notes,
            }
            for m in materials
        ],
        "count": len(materials),
    })


@toutou_bp.route("/platform-specs")
def get_platform_specs():
    """获取所有平台素材规格"""
    return jsonify(_adapter.get_platform_specs())


# ══════════════════════════════════════════════════════════════════
#  渠道选择 API
# ══════════════════════════════════════════════════════════════════

@toutou_bp.route("/channels", methods=["POST"])
def select_channels():
    """
    渠道选择 + 预算分配
    
    Request:
        {
            "content": {"topic": "人格测试", "type": "quiz", "formats": ["短视频", "图文"], "goal": "conversion"},
            "target_audience": {"age": "18-35", "interests": ["心理", "自我提升"]},
            "budget_daily": 500,
            "max_channels": 4,
            "historical_roi": {"douyin": 3.0, "xiaohongshu": 2.5}
        }
    """
    data = request.get_json() or {}
    content = data.get("content", {})
    target = data.get("target_audience", {})
    budget = float(data.get("budget_daily", 500))
    max_ch = int(data.get("max_channels", 4))
    hist_roi = data.get("historical_roi")

    plan = _selector.select(
        content=content,
        target_audience=target,
        budget_daily=budget,
        max_channels=max_ch,
        historical_roi=hist_roi,
    )

    # Store plan
    global _current_plan
    _current_plan = plan

    return jsonify({
        "total_budget": plan.total_budget,
        "daily_budget": plan.daily_budget,
        "summary": plan.summary,
        "channels": [
            {
                "channel": c.channel,
                "channel_name": c.channel_name,
                "budget": c.budget,
                "budget_pct": c.budget_pct,
                "daily_impression_est": c.daily_impression_est,
                "daily_click_est": c.daily_click_est,
                "estimated_cpc": c.estimated_cpc,
                "estimated_ctr": c.estimated_ctr,
                "roi_score": c.roi_score,
                "audience_match": c.audience_match,
                "bid_recommendation": c.bid_recommendation,
                "targeting": c.targeting,
                "notes": c.notes,
            }
            for c in plan.channels
        ],
        "ab_test_groups": plan.ab_test_groups,
        "risk_notes": plan.risk_notes,
    })


@toutou_bp.route("/channel-profiles")
def get_channel_profiles():
    """获取渠道信息"""
    return jsonify(_selector.get_channel_profiles())


# ══════════════════════════════════════════════════════════════════
#  出价优化 API
# ══════════════════════════════════════════════════════════════════

@toutou_bp.route("/bid/optimize", methods=["POST"])
def optimize_bid():
    """
    出价优化建议
    
    Request:
        {
            "channel": "douyin",
            "goal": "conversion",
            "daily_budget": 500,
            "target_cpa": 30,
            "target_roi": 2.0,
            "competition_level": "medium",
            "is_new_campaign": true
        }
    """
    data = request.get_json() or {}
    channel = data.get("channel", "douyin")
    goal = data.get("goal", "conversion")
    daily_budget = float(data.get("daily_budget", 500))
    target_cpa = float(data.get("target_cpa", 30))
    target_roi = float(data.get("target_roi", 2.0))
    competition = data.get("competition_level", "medium")
    is_new = data.get("is_new_campaign", True)

    rec = _optimizer.optimize(
        channel=channel,
        goal=goal,
        daily_budget=daily_budget,
        target_cpa=target_cpa,
        target_roi=target_roi,
        competition_level=competition,
        is_new_campaign=is_new,
    )

    return jsonify({
        "channel": rec.channel,
        "channel_name": rec.channel_name,
        "recommended": rec.recommended,
        "confidence": rec.confidence,
        "market_range": list(rec.market_range),
        "strategies": [
            {
                "mode": s.mode,
                "bid_amount": s.bid_amount,
                "target_cpa": s.target_cpa,
                "target_roi": s.target_roi,
                "daily_budget": s.daily_budget,
                "auto_rules": s.auto_rules,
                "notes": s.notes,
            }
            for s in rec.strategies
        ],
    })


@toutou_bp.route("/bid/compare", methods=["POST"])
def compare_bid():
    """多渠道路出价对比"""
    data = request.get_json() or {}
    channels = data.get("channels", ["douyin", "xiaohongshu", "bilibili"])
    budget = float(data.get("daily_budget", 500))
    target_cpa = float(data.get("target_cpa", 30))

    recs = _optimizer.compare_channels(channels, budget, target_cpa)

    return jsonify([
        {
            "channel": r.channel,
            "channel_name": r.channel_name,
            "recommended": r.recommended,
            "confidence": r.confidence,
            "market_range": list(r.market_range),
            "strategies_count": len(r.strategies),
        }
        for r in recs
    ])


# ══════════════════════════════════════════════════════════════════
#  ROI 监控 API
# ══════════════════════════════════════════════════════════════════

@toutou_bp.route("/roi/record", methods=["POST"])
def record_roi():
    """记录ROI数据点"""
    data = request.get_json() or {}
    snapshot = _monitor.record(
        channel=data.get("channel", ""),
        campaign_id=data.get("campaign_id", ""),
        spend=float(data.get("spend", 0)),
        revenue=float(data.get("revenue", 0)),
        impressions=int(data.get("impressions", 0)),
        clicks=int(data.get("clicks", 0)),
        conversions=int(data.get("conversions", 0)),
    )
    return jsonify({
        "channel": snapshot.channel,
        "roi": snapshot.roi,
        "cpa": snapshot.cpa,
        "alert_level": snapshot.alert_level,
        "alert_message": snapshot.alert_message,
    })


@toutou_bp.route("/roi/summary")
def roi_summary():
    """ROI汇总"""
    channel = request.args.get("channel", "")
    summary = _monitor.get_channel_summary(channel, channel_name=channel)
    return jsonify({
        "channel": summary.channel,
        "total_spend": summary.total_spend,
        "total_revenue": summary.total_revenue,
        "roi": summary.roi,
        "total_impressions": summary.total_impressions,
        "total_clicks": summary.total_clicks,
        "total_conversions": summary.total_conversions,
        "avg_cpa": summary.avg_cpa,
        "avg_ctr": summary.avg_ctr,
        "avg_cvr": summary.avg_cvr,
        "trend": summary.trend,
        "alert_level": summary.alert_level,
        "campaigns": summary.campaigns,
    })


@toutou_bp.route("/roi/all-summaries")
def all_roi_summaries():
    """所有渠道ROI汇总"""
    names = {
        "douyin": "抖音", "xiaohongshu": "小红书", "bilibili": "B站",
        "oceanengine": "巨量引擎", "wechat_ads": "微信广告",
    }
    summaries = _monitor.get_all_summaries(names)
    return jsonify([
        {
            "channel": s.channel,
            "channel_name": s.channel_name,
            "total_spend": s.total_spend,
            "total_revenue": s.total_revenue,
            "roi": s.roi,
            "total_impressions": s.total_impressions,
            "total_clicks": s.total_clicks,
            "total_conversions": s.total_conversions,
            "avg_cpa": s.avg_cpa,
            "avg_ctr": s.avg_ctr,
            "avg_cvr": s.avg_cvr,
            "trend": s.trend,
            "alert_level": s.alert_level,
            "campaigns": s.campaigns,
        }
        for s in summaries
    ])


@toutou_bp.route("/roi/rules")
def meltdown_rules():
    """获取熔断规则"""
    return jsonify(_monitor.get_meltdown_protection_rules())


# ══════════════════════════════════════════════════════════════════
#  投放操作 API
# ══════════════════════════════════════════════════════════════════

@toutou_bp.route("/launch", methods=["POST"])
def launch_campaign():
    """
    启动投放 (Demo模式创建Mock计划)
    
    Request:
        {
            "platform": "oceanengine",
            "name": "人格测试-抖音投放-R1",
            "budget_daily": 500
        }
    """
    data = request.get_json() or {}
    platform = data.get("platform", "oceanengine")
    name = data.get("name", "投投放送")
    budget = float(data.get("budget_daily", 500))

    # Async wrapper
    async def _launch():
        return await _bridge.create_campaign(platform, name, budget)

    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(_launch())
        loop.close()
    except Exception as e:
        result = {"success": False, "error": str(e)}

    if result.get("success"):
        _active_campaigns[platform] = {
            "campaign_id": result["campaign_id"],
            "name": name,
            "budget": budget,
            "status": "active",
            "launched_at": datetime.now().isoformat(),
        }

    return jsonify(result)


# ══════════════════════════════════════════════════════════════════
#  一键方案 API
# ══════════════════════════════════════════════════════════════════

@toutou_bp.route("/full-plan", methods=["POST"])
def generate_full_plan():
    """
    一键生成完整投放方案
    
    组合: 素材适配 + 渠道选择 + 出价优化
    
    Request:
        {
            "content": {
                "title": "你的人格画像值多少钱？",
                "body": "...",
                "cta": "免费测试",
                "key_points": ["AI分析8维度", "3分钟完成", "免费"],
                "type": "quiz",
                "formats": ["短视频", "图文"],
                "goal": "conversion"
            },
            "target_audience": {"age": "18-35", "interests": ["心理", "自我提升"]},
            "budget_daily": 500
        }
    """
    data = request.get_json() or {}
    content = data.get("content", {})
    target = data.get("target_audience", {})
    budget = float(data.get("budget_daily", 500))

    # 1. 渠道选择
    plan = _selector.select(
        content=content,
        target_audience=target,
        budget_daily=budget,
    )

    # 2. 素材适配 (选择预算最高的3个渠道)
    top_channels = [c.channel for c in plan.channels[:3]]
    materials = _adapter.adapt(
        source={
            "title": content.get("title", ""),
            "body": content.get("body", ""),
            "cta": content.get("cta", "免费测试"),
            "key_points": content.get("key_points", []),
        },
        platforms=top_channels,
    )

    # 3. 出价优化 (为主渠道优化)
    bid_recs = {}
    for c in plan.channels[:3]:
        rec = _optimizer.optimize(
            channel=c.channel,
            goal=content.get("goal", "conversion"),
            daily_budget=c.budget,
            target_cpa=30,
        )
        bid_recs[c.channel] = {
            "channel_name": rec.channel_name,
            "recommended": rec.recommended,
            "strategies": [
                {"mode": s.mode, "bid_amount": s.bid_amount, "notes": s.notes}
                for s in rec.strategies[:2]
            ],
        }

    return jsonify({
        "plan": {
            "total_budget": plan.total_budget,
            "daily_budget": plan.daily_budget,
            "summary": plan.summary,
            "channels": [
                {
                    "channel": c.channel,
                    "channel_name": c.channel_name,
                    "budget": c.budget,
                    "budget_pct": c.budget_pct,
                    "bid_recommendation": c.bid_recommendation,
                    "audience_match": c.audience_match,
                }
                for c in plan.channels
            ],
            "risk_notes": plan.risk_notes,
        },
        "materials": [
            {
                "platform": m.platform,
                "platform_name": m.platform_name,
                "title": m.title,
                "description": m.description,
                "cta": m.cta,
                "aspect_ratio": m.aspect_ratio,
                "visual_note": m.visual_note,
            }
            for m in materials
        ],
        "bidding": bid_recs,
    })


@toutou_bp.route("/ui")
def toutou_ui():
    """投投工作区 UI 页面"""
    # Render the toutou workspace HTML
    html_path = os.path.join(os.path.dirname(__file__), "templates", "toutou.html")
    if os.path.exists(html_path):
        with open(html_path, "r") as f:
            return f.read()
    return "<h1>投投工作区 UI 未找到</h1>", 404
