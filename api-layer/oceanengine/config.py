"""
OceanEngine (巨量引擎) config and endpoint registry.

API docs: https://open.oceanengine.com/labels/7/docs/1696710653812748
"""

# OAuth endpoints
OAUTH_BASE = "https://api.oceanengine.com/open_api"
TOKEN_URL = f"{OAUTH_BASE}/oauth2/advertiser/get/"  # authorization code -> token
REFRESH_URL = f"{OAUTH_BASE}/oauth2/refresh_token/"
ADVERTISER_INFO_URL = f"{OAUTH_BASE}/oauth2/advertiser/get/"

# Marketing API base (v2)
API_BASE = "https://api.oceanengine.com/open_api/2/"

# ── Campaign (广告组) ──────────────────────────────────────────────
CAMPAIGN_CREATE = f"{API_BASE}campaign/create/"     # POST
CAMPAIGN_UPDATE = f"{API_BASE}campaign/update/"     # POST
CAMPAIGN_DELETE = f"{API_BASE}campaign/delete/"     # POST
CAMPAIGN_LIST = f"{API_BASE}campaign/get/"          # GET

# ── Ad (广告计划) ──────────────────────────────────────────────────
AD_CREATE = f"{API_BASE}ad/create/"                 # POST
AD_UPDATE = f"{API_BASE}ad/update/"                 # POST
AD_DELETE = f"{API_BASE}ad/delete/"                 # POST
AD_LIST = f"{API_BASE}ad/get/"                      # GET
AD_BID_UPDATE = f"{API_BASE}ad/update/bid/"         # POST
AD_BUDGET_UPDATE = f"{API_BASE}ad/update/budget/"   # POST
AD_STATUS_UPDATE = f"{API_BASE}ad/update/status/"   # POST (pause/resume)

# ── Creative (广告创意) ────────────────────────────────────────────
CREATIVE_CREATE = f"{API_BASE}creative/create/"     # POST
CREATIVE_UPDATE = f"{API_BASE}creative/update/"     # POST
CREATIVE_LIST = f"{API_BASE}creative/get/"          # GET
CREATIVE_MATERIAL_READ = f"{API_BASE}creative/material/read/"  # GET

# ── Reports (数据报表) ─────────────────────────────────────────────
# Advertiser-level (aggregated)
REPORT_ADVERTISER = f"{API_BASE}report/advertiser/get/"  # GET
# Campaign-level
REPORT_CAMPAIGN = f"{API_BASE}report/campaign/get/"      # GET
# Ad-level (most granular)
REPORT_AD = f"{API_BASE}report/ad/get/"                  # GET
# Creative-level
REPORT_CREATIVE = f"{API_BASE}report/creative/get/"      # GET

# ── DMP / Audiences (人群管理) ─────────────────────────────────────
DMP_AUDIENCE_UPLOAD = f"{API_BASE}dmp/custom_audience/push_v2/"  # POST
DMP_AUDIENCE_READ = f"{API_BASE}dmp/custom_audience/read/"       # GET
DMP_AUDIENCE_LIST = f"{API_BASE}dmp/custom_audience/select/"     # GET
DMP_DATA_SOURCE_UPLOAD = f"{API_BASE}dmp/data_source/file/upload/"  # POST

# ── Tools ─────────────────────────────────────────────────────────
TOOLS_AD_CONVERT = f"{API_BASE}tools/ad_convert/read/"           # GET 转化ID查询
TOOLS_INDUSTRY = f"{API_BASE}tools/industry/get/"                # GET 行业查询
TOOLS_LANDING_PAGE = f"{API_BASE}tools/site/get/"                # GET 落地页查询
TOOLS_BID_SUGGEST = f"{API_BASE}tools/bid/suggest/"              # GET 建议出价

# ── QPS Limits (documented, per advertiser) ───────────────────────
DEFAULT_QPS = {
    "campaign": 10,
    "ad": 6,
    "creative": 6,
    "report": 2,
    "dmp": 2,
    "tools": 2,
}
