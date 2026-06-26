# 心因引擎 · Psych-Engine

> **项目类型**: Flask Web 应用 | **端口**: 8899 | **Phase**: 0 ✅ → 1
> **路由**: 用户端测试 + 结果分享 + 广告管理 + API

---

## 架构

```
psych-engine/
├── app.py                  # 主服务（Flask + 路由 + 引擎）
├── questions.json          # 16道测试题 + 8维度定义
├── data/                   # 运行时数据（JSONL 追加写）
│   ├── users.jsonl         #   用户记录 (user_id/昵称/IP/UA)
│   └── results.jsonl       #   测试结果 (8维得分/16题答案)
├── templates/
│   ├── test.html           #   用户端测试页（移动优先·昵称收集·进度动画）
│   ├── result.html         #   结果页（分享卡片·Canvas导出PNG·复制链接）
│   └── ads.html            #   广告投放管理页（跨渠道状态·Demo模式）
├── static/                 #   静态资源（当前空，保留）
└── ad_platforms/           #   广告平台适配
    ├── __init__.py         #     AdManager 工厂
    ├── base.py             #     抽象基类
    ├── douyin.py           #     抖音广告
    ├── bilibili.py         #     B站广告
    ├── xiaohongshu.py      #     小红书广告
    └── mock.py             #     Demo 模拟数据
```

---

## 功能清单

### 用户端（公开）
| 功能 | 路由 | 说明 |
|------|------|------|
| 人格测试 | `/` | 16题·昵称（选填）·进度指示·动画过渡 |
| 测试结果 | `/result` | 8维得分·认知OS总结·核心洞察·分享卡片 |
| 分享卡片 | Canvas导出 | 一键保存PNG·复制链接·适合社媒转发 |

### 控制台（管理）
| 功能 | 路由 | 说明 |
|------|------|------|
| 广告管理 | `/ads` | 跨渠道投放状态·预算调整 |
| 统计分析 | `/api/stats` | 用户总数·测试总数·各维度平均分 |
| 健康检查 | `/api/health` | 飞轮控制台心跳检测 |

### 后端引擎
| 模块 | 说明 |
|------|------|
| 8维人格计算 | `calc_scores()` — 选项分数映射 → 0-100归一化 |
| 画像生成 | `build_profile()` — 认知OS·核心优势·成长空间 |
| PRO深度报告 | `build_premium()` — 8维深度解析·推荐·AI系统配置 |
| 数据收集 | JSONL追加写 — 每次提交记录用户+结果 |

---

## 8维度模型

| ID | 维度 | 分数范围 | 等级线 |
|----|------|:--:|------|
| IM | 信息代谢 | 0-100 | ≥72极高 ≥58偏高 ≥43中等 ≥28偏低 |
| DA | 决策架构 | 同上 | |
| AS | 注意力结构 | 同上 | |
| ME | 动机引擎 | 同上 | |
| ST | 社交拓扑 | 同上 | |
| CB | 认知带宽 | 同上 | |
| FM | 反馈模式 | 同上 | |
| TB | 信任建立 | 同上 | |

---

## 启动

```bash
# 单独启动
cd workspace/projects/psych-engine
python3 app.py

# 统一启动（推荐）
./workspace/workspaces/shared/scripts/start-all.sh
```

健康检查：`curl http://localhost:8899/api/health`

---

## 依赖

- Flask (pip install flask)
- Python 3.9+
- 无数据库 — JSONL 文件存储

---

## 待完成

- [ ] 真实支付集成（当前 `/pay` 是模拟）
- [ ] OG 图片生成（微信分享预览优化）
- [ ] 结果页分享链接带上 user_id 参数（让分享可追踪）
- [ ] 析析 Agent 消费 `data/results.jsonl` 做人格聚类
- [ ] 错题/漏题后跳回机制优化
- [ ] 测试结果持久化（当前依赖 session，浏览器关闭后丢失）
