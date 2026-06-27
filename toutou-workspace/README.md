# 投投 · 投放+分发官 · 工作区

> **Phase 1**: 搭建投投工作区 + L1 API对接 | 模型: v4-flash

---

## 架构

```
toutou-workspace/
├── material_adapter.py   # 素材适配引擎 (1内容→8平台)
├── channel_selector.py   # 渠道选择+预算智能分配
├── bid_optimizer.py      # 出价优化引擎
├── roi_monitor.py        # ROI实时监控+熔断
├── api_bridge.py         # L1 API层桥接 (Demo/Real双模式)
├── app.py                # Flask Blueprint (REST APIs)
├── templates/
│   └── toutou.html       # 投投工作区 UI (单文件SPA)
└── README.md
```

---

## 功能清单

### 🎨 素材适配引擎
| 能力 | 说明 |
|------|------|
| 跨平台适配 | 1份源内容 → 8个平台规格（抖音/小红书/B站/朋友圈/知乎/微博/巨量引擎/微信广告） |
| 智能裁剪 | 标题字数自动适配、描述截断、CTA改写 |
| 视觉建议 | 按平台生成比例、配色、设计建议 |
| Hashtag生成 | 自动生成平台特定的标签 |

### 📡 渠道选择
| 能力 | 说明 |
|------|------|
| 智能推荐 | 基于内容类型+目标人群+历史ROI打分排序 |
| 预算分配 | 按渠道分数比例自动分配日预算 |
| A/B对照组 | 主渠道70/30对照组设计 |
| 风险评估 | 自动识别预算过低、渠道过多等风险 |

### 💰 出价优化
| 能力 | 说明 |
|------|------|
| 多策略推荐 | OCPM/CPC/CPM多模式出价建议 |
| 竞争感知 | 低/中/高竞争度自动调整出价倍数 |
| 自动调价规则 | CPA超限降价、成本达标放量、空耗暂停 |
| 全渠道对比 | 一表对比所有渠道的出价建议 |

### 📊 ROI实时监控
| 能力 | 说明 |
|------|------|
| 多维度指标 | ROI/CPA/CTR/CVR/消耗速度 |
| 趋势检测 | 自动判断上升/下降/稳定趋势 |
| 5级告警 | OK→Watch→Warn→Critical→Meltdown |
| 熔断保护 | CPA超标自动暂停、预算耗尽保护、空耗保护 |

---

## API 端点

全部挂载在 `/api/toutou/`:

| 端点 | 方法 | 说明 |
|------|------|------|
| `/status` | GET | 工作区状态 |
| `/connection` | GET | L1 API连接状态 |
| `/adapt` | POST | 素材适配 |
| `/platform-specs` | GET | 平台规格查询 |
| `/channels` | POST | 渠道选择+预算分配 |
| `/channel-profiles` | GET | 渠道数据 |
| `/bid/optimize` | POST | 出价优化 |
| `/bid/compare` | POST | 多渠道出价对比 |
| `/roi/record` | POST | 记录ROI数据 |
| `/roi/summary` | GET | 单渠道ROI汇总 |
| `/roi/all-summaries` | GET | 全渠道ROI汇总 |
| `/roi/rules` | GET | 熔断规则 |
| `/launch` | POST | 启动投放 |
| `/full-plan` | POST | 一键生成完整方案 |
| `/ui` | GET | 投投工作区 UI |

---

## 模式切换

### Demo模式 (当前)
```python
# 默认，无需凭证
_bridge = APIBridge(demo_mode=True)
```

### 真实API模式
```bash
# 设置环境变量后重启
export OCEANENGINE_APP_ID="your_app_id"
export OCEANENGINE_SECRET="your_secret"
export WECHAT_ADS_CLIENT_ID="your_client_id"
export WECHAT_ADS_CLIENT_SECRET="your_client_secret"
```
```python
_bridge = APIBridge(demo_mode=False)
```

---

## 访问方式

- **飞轮控制台** → 侧栏 Agent 群 → 投投
- **直接访问**: `http://localhost:8899/toutou`
- **API**: `http://localhost:8899/api/toutou/status`

---

## 依赖

- Flask (心因引擎)
- L1 API Layer (`projects/api-layer/`)
- 浏览器 (Chrome/Firefox/Safari, ES6+)

---

## 前置依赖 (阻塞项)

| 依赖 | 状态 | 备注 |
|------|------|------|
| 巨量引擎开发者账号 | ⏳ 待申请 | 需营业执照+广告账户 |
| 微信广告开发者账号 | ⏳ 待申请 | 需广告主账号+开发者认证 |
| L1 API层凭证配置 | ⏳ 待配置 | 环境变量设置 |
| OAuth回调端点 | ⏳ 待开发 | Web服务接收授权回调 |

> **当前所有功能可在Demo模式下运行和测试，无需真实凭证。**

---

## 下一步

1. **获取API凭证** (杰安): 申请巨量引擎+微信广告开发者账号
2. **OAuth对接测试**: 跑通授权流程 → 获取第一个access_token
3. **集成测试**: `tests/test_toutou_live.py` 在沙箱环境跑真实API
4. **与控控对接**: 预算管控数据流 + 异常预警联动
