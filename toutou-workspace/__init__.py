"""
投投 (Toutou) — 投放+分发官 · 工作区引擎

Phase 1: 搭建投投工作区 + L1 API对接

核心能力:
- 素材适配引擎 (1份内容 → 多平台规格)
- 渠道选择 + 定向投放
- 出价优化 + ROI实时监控

架构:
    toutou-workspace/
    ├── material_adapter.py   # 素材适配引擎
    ├── channel_selector.py   # 渠道选择 + 预算分配
    ├── bid_optimizer.py      # 出价优化引擎
    ├── roi_monitor.py        # ROI实时监控
    ├── api_bridge.py         # L1 API层桥接 (支持 Mock/Demo 模式)
    ├── app.py                # Flask Blueprint
    └── __init__.py           # 本文件
"""

from material_adapter import MaterialAdapter, PlatformSpec, AdaptedMaterial
from channel_selector import ChannelSelector, ChannelPlan, ChannelAllocation
from bid_optimizer import BidOptimizer, BidStrategy, BidRecommendation
from roi_monitor import ROIMonitor, ROISnapshot, AlertLevel
from api_bridge import APIBridge

__all__ = [
    "MaterialAdapter", "PlatformSpec", "AdaptedMaterial",
    "ChannelSelector", "ChannelPlan", "ChannelAllocation",
    "BidOptimizer", "BidStrategy", "BidRecommendation",
    "ROIMonitor", "ROISnapshot", "AlertLevel",
    "APIBridge",
]
