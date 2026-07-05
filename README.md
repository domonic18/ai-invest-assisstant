# AI Invest Assistant — 智能投研数据平台

面向投资分析场景的**数据采集 → 清洗入库 → 智能分析 → 可视化展示**全链路平台，
提供 **Web 端 + 微信小程序** 双端访问能力。

## 核心能力

| 能力 | Web 端 | 小程序端 |
|------|--------|----------|
| 产业链图谱分析 | ✅ 完整交互式图谱 | ❌ |
| 集合竞价可视化 | ✅ | ✅ 核心功能 (ec-canvas) |
| K线分析 | ✅ 完整K线 | ✅ 缩略K线 |
| 资金流向 | ✅ 桑基图 | ❌ |
| 财务体检 | ✅ 完整报告 | ❌ |
| 研报阅读 | ✅ 全文阅读 | ✅ 摘要速览 |
| 热点追踪 | ✅ 完整页面 | ✅ 速报推送 |
| AI 产业链分析 | ✅ | ✅ 精简摘要 |
| 产业链突破点 | ✅ 完整页面 | ✅ 速报卡片 |
| 自选股管理 | ✅ | ✅ |

## 架构概览

```
                     浏览器 (Web端)         微信小程序 (移动端)
                           │                      │
                      HTTPS API              wx.request
                           │                      │
              ┌────────────┴──────────────────────┴────────────┐
              │          腾讯云 SCF Web 函数                    │
              │     Docker 镜像 (Nginx + FastAPI + React)      │
              └─────────────────────┬──────────────────────────┘
                                    │
              ┌─────────────────────┴──────────────────────────┐
              │          腾讯云 SCF Job 函数 (异步采集)         │
              │     Timer 触发器 → Scrapy + akshare + Playwright│
              └─────────────────────┬──────────────────────────┘
                                    │
              ┌─────────────────────┴──────────────────────────┐
              │          腾讯云轻量应用服务器                    │
              │     PostgreSQL + Redis + ES + MinIO + Milvus   │
              └────────────────────────────────────────────────┘
```

## 技术栈

| 层 | 技术 |
|---|------|
| 数据采集 | Scrapy, akshare, Playwright |
| 后端 | FastAPI, Python 3.11+ |
| Web 前端 | React 18, TypeScript, Vite |
| 微信小程序 | Taro 4, React, ec-canvas |
| 可视化 | ECharts, AntV/G6, D3.js |
| 存储 | PostgreSQL(TimescaleDB), Elasticsearch, MinIO, Milvus |
| AI Agent | Codex Skill 体系 |
| 部署 | 腾讯云 SCF + 轻量应用服务器 |

## 项目结构

```
crawler/
├── docs/arch/                  # 架构设计文档 ×8
├── backend/                    # FastAPI + 采集模块（规划中）
├── web/                        # React Web 端（规划中）
├── miniapp/                    # Taro 微信小程序（规划中）
├── shared/                     # Web + 小程序共享代码（规划中）
├── skills/                     # Codex Skill ×5
├── docker/                     # Nginx/Supervisor/Job 配置（规划中）
├── db/init/                    # 数据库初始化 SQL（规划中）
└── docker-compose.infra.yml    # 轻量服务器基础设施编排（规划中）
```

## 快速开始

### 部署基础设施

```bash
# 轻量服务器
ssh root@<IP>
curl -fsSL https://get.docker.com | sh
docker compose -f docker-compose.infra.yml up -d
```

### 构建镜像

```bash
docker build -t web-api:latest -f Dockerfile .
docker build -t collector:latest -f Dockerfile.collector .
```

### 本地开发

```bash
# 后端
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Web 前端
cd web && pnpm install && pnpm dev  # → localhost:5173

# 小程序
cd miniapp && npm install && npm run dev:weapp
# 打开微信开发者工具导入 miniapp/dist/
```

## 文档

完整架构设计参见 [docs/arch/](./docs/arch/)。

## License

MIT — 详见 [LICENSE](./LICENSE)
