# AI Invest Assistant — 智能投研数据平台

面向投资分析场景的**数据采集 → 清洗入库 → 智能分析 → 可视化展示**全链路平台。

## 核心能力

| 能力域 | 内容 |
|--------|------|
| 行情研究 | 多周期 K 线 / 集合竞价趋势 / 板块资金流（河流图 + 排名）/ 宏观指数监测 |
| 每日复盘 | 指数统计 / 涨停复盘 / AI 大盘综述（可模块级编辑）/ 自选股行情卡 |
| AI 分析 | 产业链版本化分析 / 涨停归因 / 自选股每日分析 / 研报财报摘要 / 异动检测与归因 / AI 智能画线 / AI 选股 |
| 资讯与知识 | 财联社电报准实时 / 资讯重要度分级 / 热点主题聚类 / 投资日历 / 知识库检索问答 |
| AI 助手 | 全局对话面板（deepagents 流式 + 工具调用 + 会话持久化 + 页面事件回写） |
| 模拟交易 | 掘金线上仿真（账户同步 / 下单撤单 / NAV 轨迹 / K 线交易标记） |
| 平台能力 | 技能广场（zip 分发 / 自定义技能）/ 用户设置（配色 / 均线 / AI 配额）/ 后台管理（21 模块） |

## 架构概览

```
┌──────────────────────────────────────────────┐
│ 用户浏览器（桌面 / 移动 · 响应式单端）       │
└──────────────────┬───────────────────────────┘
                   │ HTTPS（SPA + /api/* 同源）
                   ▼
┌──────────────────────────────────────────────────────────────────┐
│ SCF Web 函数 — web-api 一体镜像（:9000）                         │
│ React SPA + FastAPI 单 uvicorn 进程（SPA 静态托管）· SSE 流式    │
│ deepagents 助手对话进程内承载 · 预置并发保冷启动 · 上限 900s      │
└──────────────────────┬──────────────────────┬────────────────────┘
                       │ 公网直连（读写）      │ S3 协议
                       ▼                      ▼
┌──────────────────────────────────────┐   ┌────────────────────┐
│ 轻量应用服务器 2C4G                   │   │ COS 对象存储       │
│ 数据层 postgres/timescale · redis    │   │ 研报/财报 PDF      │
│ 任务层 celery-beat + 双 worker       │   │ 知识库文件         │
│   （realtime+batch / heavy 并发=1）  │   │ pg_dump 备份目标   │
│ collector-stream（财联社电报）       │   └────────────────────┘
│ douyin-signer / paper-trade sidecar  │
└──────────────────────────────────────┘
```

完整架构设计见 [docs/arch/](./docs/arch/)（终态方案，00-09 十篇）。

## 技术栈

| 层 | 技术 |
|---|------|
| 后端 API | FastAPI, Python 3.10+, SQLAlchemy 2.0, Pydantic 2.7 |
| Web 前端 | React 18, TypeScript, Vite, TanStack Query, Zustand |
| AI Agent | deepagents (LangChain/LangGraph) + YAML Prompts + Skills + MCP |
| 数据采集 | 自研 collector runtime, Celery, httpx / akshare / curl_cffi |
| 可视化 | ECharts, AntV/G6 v5, D3.js |
| 存储 | PostgreSQL (TimescaleDB, pg_trgm + pgvector halfvec 混合检索), Redis, COS (S3 兼容) |
| 部署 | 腾讯云 SCF（web-api 一体镜像）+ 轻量服务器（采集与数据）+ GitHub Actions → TCR |
| Python 包管理 | uv |

## 项目结构

```
ai-invest-assisstant/
├── backend/
│   ├── app/                    # FastAPI 应用（api/services/repositories/models/schemas/agent）
│   ├── collector/              # 采集 runtime（core/runtime/specs/spiders/stores）
│   ├── pyproject.toml          # uv 依赖配置
│   ├── uv.lock                 # 依赖锁定文件
│   └── tests/                  # pytest 单元/集成测试
├── web/                        # React Web 端
│   ├── src/                    # 前端源码
│   └── e2e/                    # Playwright E2E 测试
├── shared/                     # 前后端共享契约（独立 npm 包：endpoints + types 17 域）
├── skills/                     # Skill 分发单元（SKILL.md + prompt.yaml 自包含目录）
├── docker/                     # Docker 镜像与数据库初始化/迁移
│   ├── web/                    # web-api 一体镜像（单 uvicorn :9000）
│   ├── collector/              # 采集镜像（beat/worker/stream/CLI）
│   ├── signer/                 # douyin-signer 签名 sidecar
│   ├── paper-trade/            # 掘金仿真 REST 网关 sidecar
│   └── database/               # init-scripts + migrations（幂等 SQL）
├── docs/                       # arch（终态架构）/ plan（计划）/ requirement / prototypes
├── qa/                         # 黑盒集成 QA 测试（独立 uv 项目）
├── CLAUDE.md / backend/CLAUDE.md / web/CLAUDE.md   # AI 上下文
├── docker-compose.yml          # 全栈编排（本地/生产共用）
├── docker-compose.prod.yml     # 生产叠加（端口/环境变量/资源限制）
└── .env.example                # 环境变量模板
```

## 快速开始

```bash
# 本地全栈（docker compose）
cp .env.example .env
docker compose up -d          # web :9000，健康检查 /health

# 生产服务器（显式 prod 叠加，服务器不构建）
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d --wait --remove-orphans --no-build
```

### 构建镜像

```bash
docker build -t web-api:latest -f docker/web/Dockerfile .
docker buildx build --platform linux/amd64 -f docker/collector/Dockerfile -t collector:latest --load .
```

### 本地开发（不进容器）

项目使用 `uv` 管理 Python 依赖，`npm` 管理前端依赖。开始之前，请确保已安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)。

```bash
# 基础设施（PostgreSQL、Redis、MinIO）
docker compose up -d postgres redis minio

# 后端（:8000）
cd backend && uv sync
uv run uvicorn app.main:app --reload --port 8000

# Web 前端（:5173，Vite 代理至后端）
cd web && npm install
npm run dev

# 模拟盘 sidecar（可选）
docker compose up -d paper-trade
```

### 常用命令

```bash
# 后端类型检查 / lint / 测试
cd backend
uv run mypy app/
uv run ruff check .
uv run pytest -m unit

# 前端类型检查 / lint / 测试
cd web
npm run typecheck
npm run lint
npm run test:unit
```

## 文档

- [docs/arch/](./docs/arch/) — 架构设计（终态方案）
- [docs/plan/development-plan.md](./docs/plan/development-plan.md) — 功能开发计划（批次与状态真相源）

## License

MIT — 详见 [LICENSE](./LICENSE)
