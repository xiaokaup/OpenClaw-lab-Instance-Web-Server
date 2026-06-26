"""
WeChat Ads (微信广告) config and endpoint registry.

API docs: https://developers.weixin.qq.com/doc/ads/

WeChat Ads uses a slightly different structure from OceanEngine:
- Adgroup (广告组) → Ad (广告) → Creative (创意)
- Reports are at adgroup/creative level
"""

# OAuth endpoints
OAUTH_BASE = "https://api.weixin.qq.com"
TOKEN_URL = f"{OAUTH_BASE}/oauth2/token"
REFRESH_URL = f"{OAUTH_BASE}/oauth2/refresh_token"

# Ads API base (Marketing API)
API_BASE = "https://api.weixin.qq.com/marketing"

# ── Campaign / Adgroup (广告组) ────────────────────────────────────
ADGROUP_ADD = f"{API_BASE}/adgroups/add"        # POST
ADGROUP_UPDATE = f"{API_BASE}/adgroups/update"  # POST
ADGROUP_GET = f"{API_BASE}/adgroups/get"        # GET
ADGROUP_DELETE = f"{API_BASE}/adgroups/delete"  # POST

# ── Ad (广告) ──────────────────────────────────────────────────────
AD_ADD = f"{API_BASE}/ads/add"                  # POST
AD_UPDATE = f"{API_BASE}/ads/update"            # POST
AD_GET = f"{API_BASE}/ads/get"                  # GET
AD_DELETE = f"{API_BASE}/ads/delete"            # POST

# ── Creative (广告创意) ────────────────────────────────────────────
CREATIVE_ADD = f"{API_BASE}/adcreatives/add"    # POST
CREATIVE_UPDATE = f"{API_BASE}/adcreatives/update"  # POST
CREATIVE_GET = f"{API_BASE}/adcreatives/get"    # GET
CREATIVE_DELETE = f"{API_BASE}/adcreatives/delete"  # POST

# ── Reports ───────────────────────────────────────────────────────
DAILY_REPORT = f"{API_BASE}/daily_reports/get"      # GET
HOURLY_REPORT = f"{API_BASE}/hourly_reports/get"    # GET
ADGROUP_REPORT = f"{API_BASE}/adgroup_reports/get"  # GET
TARGETING_REPORT = f"{API_BASE}/targeting_reports/get"  # GET

# ── Audiences (人群管理) ──────────────────────────────────────────
AUDIENCE_ADD = f"{API_BASE}/custom_audiences/add"    # POST
AUDIENCE_GET = f"{API_BASE}/custom_audiences/get"    # GET
AUDIENCE_DELETE = f"{API_BASE}/custom_audiences/delete"  # POST
AUDIENCE_FILE_ADD = f"{API_BASE}/custom_audience_files/add"  # POST

# ── Tools / Targeting ─────────────────────────────────────────────
TARGETING_TAGS = f"{API_BASE}/targeting_tags/get"    # GET 定向标签查询
ADCREATIVE_TEMPLATE = f"{API_BASE}/adcreative_templates/get"  # GET 创意规格
ESTIMATE = f"{API_BASE}/estimation/get"              # GET 预估覆盖

# WeChat-specific placement sites
PLACEMENT = {
    "moments": "SITE_SET_MOMENTS",       # 朋友圈
    "official_account": "SITE_SET_WECHAT", # 公众号
    "channels": "SITE_SET_CHANNELS",     # 视频号
    "mini_program": "SITE_SET_MINI_PROGRAM", # 小程序
    "wechat_search": "SITE_SET_WECHAT_SEARCH",  # 搜一搜
}

# QPS limits (documented)
DEFAULT_QPS = {
    "adgroup": 10,
    "ad": 10,
    "creative": 10,
    "report": 5,
    "audience": 5,
    "tools": 5,
}
