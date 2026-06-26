"""
WeChat Ads (微信广告) Marketing API client.

Covers: 朋友圈/公众号/视频号/小程序 全广告位投放.
"""

from .auth import WeChatAdsAuth
from .client import WeChatAdsClient
from . import config

__all__ = ["WeChatAdsAuth", "WeChatAdsClient", "config"]
