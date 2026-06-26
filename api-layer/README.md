# L1 — 原生 API 层

> **状态**: 开发中 | 覆盖: 巨量引擎 + 微信广告 | 目标: 完整程序化投放

---

## 架构

```
api-layer/
├── common/              # 通用基础设施
│   ├── base_client.py   # 异步HTTP客户端 (auth/rate-limit/retry/error)
│   ├── errors.py        # 统一异常类型
│   ├── rate_limiter.py  # Token-bucket限流器
│   ├── retry.py         # 指数退避重试
│   └── models.py        # 跨平台统一数据模型
│
├── oceanengine/         # 巨量引擎 (抖音/头条/穿山甲)
│   ├── config.py        # API端点注册
│   ├── auth.py          # OAuth2 (授权码+刷新)
│   └── client.py        # 完整API客户端
│        ├── Campaign CRUD
│        ├── Ad CRUD + 出价/预算/状态调整
│        ├── Creative CRUD
│        ├── Report (ad/campaign/advertiser级别)
│        ├── DMP 人群推送 (析析→投投桥梁)
│        └── Tools (建议出价)
│
├── wechat_ads/          # 微信广告 (朋友圈/公众号/视频号)
│   ├── config.py        # API端点注册 + 广告位定义
│   ├── auth.py          # OAuth2 (client_credentials)
│   └── client.py        # 完整API客户端
│        ├── Adgroup CRUD
│        ├── Ad CRUD
│        ├── Creative CRUD
│        ├── Report (daily/hourly/adgroup/creative)
│        ├── Audience 自定义人群
│        └── Tools (定向标签/预估覆盖)
│
└── README.md
```

---

## 设计原则

### 1. 统一数据模型
两个平台的API结构不同，但 `common/models.py` 定义了 `Campaign`, `AdGroup`, `Creative`, `ReportRow` 统一模型。上层代码（投投/控控）只和这些模型交互，不关心底层平台差异。

### 2. 异步优先
全链路 `async/await`，基于 `httpx.AsyncClient`。单实例可以管理数百个并发请求。

### 3. 故障隔离
- 每个平台独立 `BaseClient` 实例
- Token自动刷新（401 → 刷新 → 重试）
- 429自动退避
- 5xx自动重试（最多3次）

### 4. 生产就绪
- 所有金额统一用「分」(fen)存储，避免浮点精度问题
- 限流器防止撞QPS上限
- 结构化日志 (`logging.getLogger("api-layer.xxx")`)
- 统一异常类型，上层的 `try/except` 不需要区分平台

---

## 使用示例

```python
import asyncio
from api_layer.oceanengine import OceanEngineAuth, OceanEngineClient
from api_layer.wechat_ads import WeChatAdsAuth, WeChatAdsClient

async def main():
    # ── 巨量引擎 ──
    oe_auth = OceanEngineAuth(
        app_id="your_app_id",
        secret="your_secret",
    )
    await oe_auth.get_token(auth_code="user_auth_code")
    
    oe = OceanEngineClient(oe_auth)
    
    # 创建广告组
    campaign = await oe.create_campaign(
        advertiser_id="12345",
        name="人格测试-投放-R1",
        budget=50000,  # 500元/天
    )
    
    # 拉报表
    report = await oe.get_ad_report(
        advertiser_id="12345",
        start_date="2026-06-20",
        end_date="2026-06-25",
    )
    
    # ── 微信广告 ──
    wx_auth = WeChatAdsAuth(
        client_id="your_client_id",
        client_secret="your_client_secret",
    )
    await wx_auth.get_token()
    
    wx = WeChatAdsClient(wx_auth)
    
    # 创建朋友圈广告组
    wx_adgroup = await wx.create_adgroup(
        name="人格测试-朋友圈-R1",
        site_set=["SITE_SET_MOMENTS"],
        daily_budget=50000,
        gender=["MALE", "FEMALE"],
        age=["20~29", "30~39"],
    )

asyncio.run(main())
```

---

## 依赖

```
httpx>=0.27.0
python-dotenv>=1.0.0
```

安装:

```bash
pip install httpx python-dotenv
```

---

## 待完成 & 已知限制

### 巨量引擎
- [ ] 视频素材上传API
- [ ] 程序化创意（多图轮播/视频+图混合）
- [ ] 转化追踪配置API（需要先建转化目标）
- [ ] OAuth回调端点（Web服务）

### 微信广告
- [ ] 素材上传API（图片/视频需先上传到素材库）
- [ ] 视频号投放特殊参数
- [ ] 朋友圈广告审核状态轮询
- [ ] OAuth回调端点

### 通用
- [ ] 凭证管理（AppId/Secret 不应硬编码，存环境变量或密钥管理）
- [ ] 请求签名验证（巨量引擎某些接口需要）
- [ ] Webhook回调处理（接收平台异步通知）
- [ ] 集成测试（需要真实广告账户才能跑通）

---

## 下一步

1. **获取开发者凭证**: 杰安需要申请巨量引擎+微信广告的开发者账号 → 拿到 AppId/Secret
2. **OAuth对接测试**: 跑通授权流程 → 获取第一个 access_token
3. **写集成测试**: `tests/test_oceanengine_live.py` 在沙箱环境跑真实API
4. **搭建统一归因层**: 在 `common/` 下加跨平台归因逻辑
