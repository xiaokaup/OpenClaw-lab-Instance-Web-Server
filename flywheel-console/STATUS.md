# 飞轮控制台 STATUS

> 2026-06-27 10:12 CST · 全部5 Agent工作区已上线

## 可访问页面

| 页面 | URL | 状态 |
|------|-----|:--:|
| 🖥️ 飞轮控制台 | `localhost:18789/__openclaw__/canvas/flywheel/console.html` | 🟢 |
| 🧬 用户端测试 | `localhost:8899` | 🟢 |
| 📊 测试结果 | `localhost:8899/result` | 🟢 |
| 🧠 策策工作区 | `localhost:8899/cece` | 🟢 |
| 🔬 析析工作区 | `localhost:8899/xixi` | 🟢 |
| 📤 投投工作区 | `localhost:8899/toutou` | 🟢 |
| 🎯 荐荐工作区 | `localhost:8899/jianjian` | 🟢 |
| 💰 控控工作区 | `localhost:8899/kongkong` | 🟢 |
| 📊 广告管理 | `localhost:8899/ads` | 🟢 |
| 📡 API 健康 | `localhost:8899/api/health` | 🟢 |

## Agent 工作区总览

| Agent | 路由 | 工作区 | 控制台连接 | API端点 |
|:-----:|------|:---:|:--------:|---------|
| 🧠 策策 | `/cece` | cece.html (23KB) | iframe嵌入 | `/api/cece/status` `/api/cece/topics` |
| 🔬 析析 | `/xixi` | xixi.html (30KB) | 跳转链接 | 6个workspace端点 |
| 📤 投投 | `/toutou` | toutou-workspace | iframe嵌入+LIVE检测 | `/api/toutou/*` (4端点) |
| 🎯 荐荐 | `/jianjian` | jianjian.html (26KB) | iframe嵌入 | `/api/jianjian/status` `/api/jianjian/products` |
| 💰 控控 | `/kongkong` | kongkong.html (23KB) | iframe嵌入 | `/api/kongkong/status` `/api/kongkong/pricing` |

## API 端点（新增）

| 端点 | 数据 |
|------|------|
| `/api/cece/status` | 策策工作区状态（话题数·题目数·内容数）|
| `/api/cece/topics` | 活跃话题列表+爆款分 |
| `/api/jianjian/status` | 荐荐工作区状态（产品数·分群数）|
| `/api/jianjian/products` | 产品目录（12产品×3层级）|
| `/api/kongkong/status` | 控控工作区状态（预算池·渠道分配·告警）|
| `/api/kongkong/pricing` | 定价分层数据+产品目录 |
