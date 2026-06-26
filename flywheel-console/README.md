# 飞轮控制台 · Flywheel Console

> **项目类型**: Canvas 托管 SPA | **入口**: `/__openclaw__/canvas/flywheel/console.html`
> **架构**: 单文件 SPA · 双视角（CTO/CEO）· 实时系统健康检测

---

## 架构

```
flywheel-console/
├── console.html            # 单文件 SPA（HTML+CSS+JS，零依赖）
└── README.md               # 本文档
```

> Canvas 插件通过 symlink 托管：`canvas/flywheel/console.html` → 本项目

---

## 双视角

| 视角 | 角色 | 仪表盘类型 | 侧栏导航 |
|------|------|-----------|---------|
| 杰安 | CTO | 技术仪表盘 | 系统健康·API凭证·Agent群·任务看板 |
| 河山 | CEO | 商业仪表盘 | Phase进展·市场·预算·定价·路线图 |

通过顶部 `⚙️ 杰安 / 💼 河山` 切换。

---

## 功能清单

### CTO 视角（杰安）
| 页面 | 功能 |
|------|------|
| 技术仪表盘 | 4项指标卡·系统健康(6项实时检测)·Agent卡片·最近任务 |
| 系统管理 | 已部署系统列表（含直达链接） |
| API 凭证 | 平台API申请状态跟踪 |
| Agent 工作区 | 策策/析析/投投/荐荐/控控 各页面（当前占位） |
| 任务看板 | 链接到 Workboard API（`/api/workboard/cards`） |

### CEO 视角（河山）
| 页面 | 功能 |
|------|------|
| 商业仪表盘 | Phase进展·市场机会·团队介绍 |
| 市场数据 | Phase 2 占位 |
| 竞品动态 | Phase 2 占位 |
| 预算总览 | Phase 2 占位 |
| 单位经济学 | CAC/LTV/ROI（Phase 2） |
| 定价策略 | Phase 2 占位 |
| 产品路线图 | Phase 1 占位 |

### 实时检测
- **系统健康面板**：页面加载时自动 `fetch /api/health` 检测 Flask 在线状态（绿色/红色）
- **实时统计**：`fetch /api/stats` 拉取用户数/测试数
- **Workboard集成**：拉取 Control UI API 显示最近任务

---

## 技术要点

- **零框架**：纯 Vanilla HTML/CSS/JS，无 React/Vue 依赖
- **Canvas 托管**：通过 OpenClaw Canvas 插件提供 HTTP 服务
- **CORS 跨域**：通过 Flask CORS 支持跨端口 API 调用
- **单文件 SPA**：所有页面内联渲染，JS 路由切换

---

## 与心因引擎的关系

```
飞轮控制台 (Canvas :18789)
  │
  ├─ fetch /api/health → 检测 Flask 在线
  ├─ fetch /api/stats  → 拉取实时数据
  └─ 链接 → http://localhost:8899 (用户端测试页)
```

---

## 待完成

- [ ] 河山视角页面填充真实数据（Phase 2）
- [ ] Agent 工作区页面实现（Phase 1 — Agent 直接操作页面）
- [ ] Workboard API 真实对接（当前 fallback 到占位文案）
- [ ] 系统健康面板增加 Canvas 自身状态检测
- [ ] 暗色/亮色主题切换
