# AI Invest Assistant 开发计划

## 1. 项目现状

### 1.1 已交付资产

| 资产 | 状态 | 说明 |
|------|------|------|
| 需求文档 | 已完成 | `docs/requirement/01-requirement.md` 定义 P0-P3 功能矩阵、版本边界、非功能需求 |
| 架构设计 | 已完成 | `docs/arch/00-overview.md ~ 07-testing.md` 覆盖总体架构、数据源、采集、存储、AI Agent、前端、部署、测试 |
| Web 原型 | 已完成 | `docs/prototypes/*.html` 共 13 个页面 |
| AI Skill | 已完成 | `skills/*/` 下 5 个 SKILL.md |
| 后端工程 | 已完成主体 | `backend/`：FastAPI 核心、17 个业务 Service、20+ API 路由、15 个采集器、Redis 队列 worker、单元测试 30 个文件 |
| Web 前端 | 已完成主体 | `web/`：React + Vite + TypeScript，24 个页面，Ant Design 组件化，认证/仪表盘/产业链/个股/后台管理已上线 |
| 共享层 | 已发布 | `shared/`：前后端共享类型与 API 常量，已作为 npm 包发布并在 backend 通过软链接/构建引用 |
| Docker 与部署 | 已完成骨架 | `docker/`、``docker-compose.yml``、``.env.example``、Nginx/SCF 镜像、数据库初始化脚本 |

### 1.2 工程目录健康度

```
backend/                          # FastAPI + 采集模块（已落地）
├── pyproject.toml                # uv 依赖与工具配置 ✅
├── uv.lock                       # 锁定文件 ✅
web/                              # React + Vite + TypeScript ✅
miniapp/                          # Taro 4 +  React 微信小程序（V1.1 阶段启动）⏸️
shared/                           # Web + 小程序共享类型/工具/API 封装 ✅
docker/                           # Docker 镜像与数据库初始化 ✅
├── web/                          # Web 函数 Dockerfile + Nginx 配置 ✅
├── collector/                    # SCF Job / worker Dockerfile + 入口脚本 ✅
└── database/                     # 数据库初始化 SQL ✅
    └── init-scripts/
├── docker-compose.yml            # 全栈本地/生产编排 ✅
docker-compose-dev.yml            # 开发环境编排 ⏸️（可选）
docker-compose.infra.yml          # 轻量服务器基础设施编排 ⏸️（可选）
.env.example                      # ✅
Makefile                          # ⏸️（待完善）
CLAUDE.md                         # 项目级 AI 上下文 ✅
backend/CLAUDE.md                 # 后端 AI 上下文 ✅
web/CLAUDE.md                     # 前端 AI 上下文 ✅
```

### 1.3 开发策略

- **数据先行**：先完成 schema、采集器、清洗管道与种子数据，再启动前后端。
- **接口契约先行**：`shared/` 目录下的类型与端点常量作为后端、Web、小程序三方的法律依据。
- **Skill 与代码解耦**：AI 分析优先通过 Skill + Python Agent SDK（PydanticAI / OpenAI Agents SDK）实现，复杂场景再补充 Python 代码。
- **串并混合**：数据层 → 后端 API → Web 端 → 后台/MCP → 部署优化 → 小程序，前后端可部分重叠推进；小程序待主产品稳定后再启动。

## 2. 开发目标

在约 **18-22 周**内交付 **V1.0 MVP**（后端 + Web + 后台管理/MCP），并在此基础上用约 **3-4 周**完成微信小程序：

1. 基础设施可一键部署（轻量服务器 Docker Compose + SCF 镜像）。
2. 数据采集管道打通：行情、公告/新闻、财报、研报、集合竞价、资金流向。
3. 后端 API 支撑 Web 端，具备 JWT 认证与基础限流。
4. Web 端上线：仪表盘、产业链全景、热点追踪、集合竞价复盘、资金流向、个股详情、研报中心、用户设置。
5. 5 个核心 AI Skill 可通过后端 API 被调用并返回结构化结果。
6. 后台管理系统支持用户/股票/研报/新闻/采集任务的 CRUD 与监控。
7. API-KEY 与 MCP 接口就绪，支持外部 AI 工具接入。
8. **V1.1 阶段**：待 Web 端与后端整体稳定、生产环境运行正常后，再启动微信小程序开发。

## 3. 分阶段路线图

### 阶段 0：项目启动与工程骨架（第 1-2 周）

**目标**：搭建可运行的多模块工程骨架，建立共享契约、本地开发流程与 CI 基础。

**交付物**：后端 / Web / shared / docker / qa 工程目录、小程序骨架（可选）、顶层配置、CI 与 lint 脚本。

**验收标准**：`make backend` 与 `make web` 能分别启动后端与 Web 前端；`make lint` 通过；`uv run pytest -m unit` 与 `npm run test:unit` 可执行（测试用例可逐步补充）；小程序工程目录可编译（可选）。

**实际状态**：✅ 已完成（commit `cd2b987`）。`backend/`、`web/`、`shared/`、`docker/`、`CLAUDE.md` 均已落地，`uv` 与 `npm` 开发流已跑通。

**剩余任务**：完善 `Makefile`、补齐 `docker-compose-dev.yml` 与 `docker-compose.infra.yml`（可选）。

### 开发环境说明

- **Python 后端统一使用 `uv` 管理依赖**，不再使用 `pip` + `requirements.txt`。
  - 进入 `backend/` 后执行 `uv sync` 同步环境（含 dev 依赖）。
  - 运行服务：`uv run uvicorn app.main:app --reload --port 8000`
  - 运行测试：`uv run pytest -m unit`
  - 类型检查：`uv run mypy app/`
  - 代码 lint：`uv run ruff check .`
- **前端使用 npm**，进入 `web/` 后执行 `npm install`。
- **AI 上下文文件**：修改代码前请先阅读 `CLAUDE.md`、`backend/CLAUDE.md`、`web/CLAUDE.md`。

### 阶段 1：数据层与采集管道（第 3-6 周）

**目标**：建立可落地真实数据的存储层与采集管道。

**交付物**：
- PostgreSQL + TimescaleDB schema、Redis key 设计、ES 索引模板、MinIO bucket、Milvus collection
- 采集器基类、清洗管道、行情/新闻/公告/公司信息采集器
- SCF Job 入口、本地调度、开发种子数据

**验收标准**：`docker compose -f docker-compose.infra.yml up -d` 拉起全部中间件；行情与新闻采集稳定入库；幂等写入。

**实际状态**：🟡 主体完成，持续增强中。已落地 15 个采集器（行情、新闻、公告、公司信息、IPO、资金流向、龙虎榜、研报、财报、基金持仓、集合竞价、宏观经济等），新增 Redis 队列 worker 与本地 scheduler 统一执行入口，MinIO/KB 服务已接入财报文件存储。

**剩余任务**：
- 补齐 ES 索引模板与 Milvus collection 初始化脚本。
- 增加采集任务失败重试、幂等写入的端到端回归测试。
- 补充 `docker-compose.infra.yml` 用于轻量服务器一键拉起中间件。

### 阶段 2：后端 API 与 AI 集成（第 5-9 周）

> 与阶段 1 后半段重叠 2 周。

**目标**：构建支撑双端的后端 API，并接入 Python Agent SDK。

**交付物**：
- FastAPI 核心模块、JWT / 微信登录、股票数据接口、自选股接口
- 产业链 / 研报 / 热点 / 财务 / 突破点 AI 分析 API
- Skill 调用封装、后台管理前置 API、Swagger 文档、单元测试

**验收标准**：P0/P1 接口可调用并返回符合 `shared/` 类型的响应；5 个核心 Skill 可返回有效 JSON；API P95 < 500ms。

**实际状态**：🟡 核心接口已完成。research/hotspot/financial 等 P0 接口已联调（commits `598b672`、`6e60fbf`），产业链 AI 分析已接入，JWT 认证与 OAuth2 表单登录已完成，自选股接口已上线，admin 前置 API 已就绪。

**剩余任务**：
- 将 5 个核心 Skill 输出与 `shared/` 类型做回归对照，建立输出样例库。
- 补充 AI 分析接口的 P95 延迟基线与性能测试。
- 完成微信登录（当前仅支持账号密码）。

### 阶段 3：Web 前端（第 8-13 周）

> 与阶段 2 重叠 2 周。

**目标**：将 HTML 原型工程化为 React 应用并完成 API 对接。

**交付物**：登录/注册、仪表盘、产业链分析、个股详情、热点追踪、资金流向、集合竞价复盘、研报中心、用户设置，以及 K 线/G6/D3/竞价图表组件。

**验收标准**：P0 页面可访问并联调通过；产业链图谱可交互；首屏加载 < 3 秒；E2E 覆盖登录 → 仪表盘 → 产业链链路。

**实际状态**：🟡 主体完成。Ant Design 重构、登录注册、路由守卫、仪表盘、产业链、个股、热点、资金流向、集合竞价、研报中心、用户设置、后台管理页面均已实现（commits `499807e`、`267b7e7`、`1780b30` 等）。

**剩余任务**：
- 完成 Playwright E2E 核心链路（登录 → 仪表盘 → 产业链 → 个股）。
- 首屏性能基线测量与优化（目标 < 3s）。
- 补充图表组件单元测试。

### 阶段 4：后台管理与 MCP 接口（第 12-16 周）

**目标**：构建独立后台管理端，完成 API-KEY 管理与 MCP 接口暴露。

**交付物**：
- 后台管理：用户/股票/研报/新闻/采集任务 CRUD、系统监控、审计日志
- API-KEY 生命周期管理
- MCP Server：9 个 Tools + 2 个 Resources、SSE 传输、客户端配置模板

**验收标准**：管理员可通过 `/admin` 完成 P0 CRUD；MCP Tool 调用成功率 ≥ 95%。

**实际状态**：🟡 后台管理大部分完成，MCP 仅为骨架。用户/股票/研报/新闻/任务 CRUD、LLM 配置、采集渠道/任务管理、系统监控接口已实现；MCP Server 当前仅返回空 `tools` 列表（`backend/app/api/v1/mcp/server.py`），API-KEY 管理接口待确认。

**剩余任务**：
- 实现 MCP Server 的 9 Tools + 2 Resources 与 SSE 传输。
- 完成 API-KEY 创建/撤销/校验。
- 提供 Claude Desktop / Cursor 配置模板。
- 补充 MCP 集成测试（标记 `mcp`）。

### 阶段 5：部署、测试与生产加固（第 15-20 周）

**目标**：完成腾讯云部署、镜像构建、监控告警、性能优化与安全加固，达到 Web 端生产上线标准。

**交付物**：轻量服务器部署脚本、Web/Job 镜像构建、SCF 配置、域名 HTTPS、CLS 日志、监控告警、性能优化、安全加固、集成/压力测试、上线检查清单。

**验收标准**：生产环境可访问；采集任务稳定运行 3 个交易日；系统可用性 ≥ 99.5%；通过安全审查。

**实际状态**：🔴 骨架已有，生产级能力待补齐。Docker 镜像、Nginx、SCF 入口、数据库初始化已存在；CLS、监控告警、压力测试、安全审查、域名 HTTPS 自动化尚未落地。

**剩余任务**：
- 生产环境 `.env` 与密钥管理（AES-256-GCM 已落地，需审计）。
- 腾讯云 CLS/监控告警对接。
- 压力测试（100 并发）与性能调优。
- 安全审查：CORS、SQL 注入、XSS、敏感日志过滤。
- 上线检查清单与回滚方案。

### 阶段 6：微信小程序（第 20-24 周）

> 待 Web 端与后端整体稳定、生产环境运行正常后再启动。

**目标**：完成小程序端核心功能，复用共享层与后端接口。

**交付物**：首页、行情/自选股、集合竞价可视化（ec-canvas）、AI 分析页、个人中心、微信登录。

**验收标准**：可在微信开发者工具预览；集合竞价曲线正确渲染；包体积 < 2MB。

**实际状态**：⏸️ 尚未启动。

### 路线图总览

```
周次  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24
     ├────阶段0────┤✅
                   ├────────阶段1────────┤🟡
                               ├────────────阶段2────────────┤🟡
                                             ├────────────────阶段3────────────────┤🟡
                                                                       ├────阶段4────┤🟡
                                                                                   ├──────阶段5──────┤🔴
                                                                                                   ├────阶段6────┤⏸️
```

图例：✅ 已完成 / 🟡 主体完成，剩余增强 / 🔴 骨架完成，待生产加固 / ⏸️ 未启动

> 阶段 6（小程序）待 Web 端与后端整体稳定、生产环境运行正常后再启动。V1.0 MVP 以阶段 5 结束为标志。

## 4. 关键任务分解

### 阶段 0

| 任务 | 优先级 | 建议工时 | 状态 | 说明 |
|------|--------|----------|------|------|
| 后端工程骨架 | P0 | 2d | ✅ | `backend/app/`、`backend/app/prompts/`、`backend/collector/`、`backend/pyproject.toml` |
| Web 前端工程骨架 | P0 | 2d | ✅ | Vite + React + TS 已搭建 |
| shared 共享层 | P0 | 2d | ✅ | 已作为 npm 包发布并被 backend 引用 |
| Docker 镜像与数据库初始化配置 | P0 | 2d | ✅ | `docker/web/`、`docker/collector/`、`docker/database/init-scripts/` |
| 测试工程目录占位 | P0 | 1d | ✅ | `backend/tests/`、`qa/integration/`；`web/src/test/` 待建 |
| CI / lint / 开发脚本 | P0 | 1d | 🟡 | uv/npm 脚本可用，`Makefile` 待完善 |
| CLAUDE.md 上下文文件 | P0 | 0.5d | ✅ | 根目录、`backend/`、`web/` 均已完成 |
| 小程序工程骨架（可选） | P2 | 1d | ⏸️ | 仅创建目录与编译脚本 |
| 更新 README 开发指南 | P1 | 1d | ⏸️ | 待同步最新启动命令 |

### 阶段 1

| 任务 | 优先级 | 建议工时 | 状态 | 说明 |
|------|--------|----------|------|------|
| PostgreSQL schema 初始化 | P0 | 3d | ✅ | `docker/database/init-scripts/01-schema.sql` |
| Redis / ES / MinIO / Milvus 初始化 | P1 | 3d | 🟡 | Redis/MinIO 已用；ES/Milvus 初始化脚本待补齐 |
| 采集器基类与清洗管道 | P0 | 3d | ✅ | `collector/base.py`、pipelines、exporters |
| 行情采集器（日 K / 分钟 K） | P0 | 3d | ✅ | `sina_kline.py`、`ths_kline.py` |
| 新闻/公告采集器 | P0 | 3d | ✅ | `sina_news.py`、`cninfo_disclosure.py` |
| 公司基本信息采集器 | P1 | 2d | ✅ | `cninfo_profile.py` |
| 财报 / IPO / 基金持仓采集器 | P0 | 4d | ✅ | `cninfo_financial_report.py`、`cninfo_ipo.py`、`eastmoney_fund_holdings.py` 等 |
| SCF Job 入口与本地调度 | P1 | 2d | ✅ | `scf_handler.py`、`scheduler.py`、Redis worker |
| 开发环境种子数据 | P1 | 2d | ⏸️ | 待补充 |
| 采集监控与日志 | P2 | 2d | 🟡 | `collector_log` 表已存在，Dashboard 待完善 |

### 阶段 2

| 任务 | 优先级 | 建议工时 | 状态 | 说明 |
|------|--------|----------|------|------|
| FastAPI 核心模块 | P0 | 3d | ✅ | 依赖注入、异常处理、分页、Swagger |
| 用户认证接口 | P0 | 2d | ✅ | JWT + OAuth2 表单；微信登录待做 |
| 股票数据接口 | P0 | 3d | ✅ | `stocks.py`、`kline.py` |
| 自选股接口 | P1 | 2d | ✅ | `watchlist.py` |
| Python Agent SDK 与 Prompt 加载器封装 | P0 | 3d | ✅ | `llm_router`、`prompt_loader` |
| 产业链 / 研报 / 热点 / 财务 / 突破点 API | P0-P1 | 10d | 🟡 | research/hotspot/financial 已上线；突破点待确认 |
| 后台管理前置 API | P1 | 3d | ✅ | admin 模块已完成 |
| API 文档与单元测试 | P1 | 3d | 🟡 | Swagger 可用；后端单元测试 30 个，覆盖率待测量 |
| 后端集成测试 | P1 | 3d | ⏸️ | `tests/integration/` 为空 |
| Skill 输出解析与回归测试 | P1 | 2d | ⏸️ | 需建立输出样例库 |

### 阶段 3

| 任务 | 优先级 | 建议工时 | 状态 | 说明 |
|------|--------|----------|------|------|
| 前端基础框架 | P0 | 3d | ✅ | Ant Design + Tailwind + 路由守卫 |
| 登录/注册 | P0 | 2d | ✅ | 账号密码登录完成 |
| 仪表盘 | P0 | 3d | ✅ | Dashboard 页面 |
| 产业链分析页 | P0 | 5d | ✅ | ChainAnalysis + G6 图谱 |
| 个股详情页 | P0 | 4d | ✅ | StockDetail |
| 热点追踪 / 资金流向 / 集合竞价复盘 | P0 | 9d | ✅ | Hotspot、CapitalFlow、AuctionReview |
| 研报中心 / 用户设置 | P1 | 6d | ✅ | Research、Settings |
| 图表组件封装 | P0 | 4d | 🟡 | ECharts/K 线/竞价组件已用，待统一封装 |
| 前端单元测试 | P1 | 3d | ⏸️ | Vitest 已配置，测试待补充 |
| Playwright E2E 测试 | P1 | 3d | ⏸️ | 待建立 |

### 阶段 4

| 任务 | 优先级 | 建议工时 | 状态 | 说明 |
|------|--------|----------|------|------|
| 后台管理框架与用户管理 | P0 | 4d | ✅ | Admin 页面 + Users CRUD |
| 股票 / 研报 / 新闻 / 采集任务管理 | P1 | 8d | ✅ | Stocks、Reports、News、Tasks、Collector 管理 |
| LLM 配置与采集渠道管理 | P1 | 3d | ✅ | LLMConfig、CollectorChannelConfig |
| 系统监控与审计日志 | P1-P2 | 4d | 🟡 | 系统监控接口已存在，前端展示待增强 |
| API-KEY 管理 | P1 | 2d | 🔴 | 待确认接口实现 |
| MCP Server 与客户端模板 | P1 | 5d | 🔴 | 仅骨架，Tools/Resources/SSE 待实现 |

### 阶段 5

| 任务 | 优先级 | 建议工时 | 状态 | 说明 |
|------|--------|----------|------|------|
| 轻量服务器部署脚本 | P0 | 2d | 🔴 | 待提供一键部署脚本 |
| Web / Job 镜像构建与 SCF 配置 | P0 | 4d | 🟡 | Dockerfile、SCF handler 已存在；生产镜像优化待做 |
| 域名与 HTTPS | P0 | 1d | 🔴 | Nginx 配置存在，证书自动化待做 |
| 日志与监控 | P1 | 2d | 🔴 | CLS/告警未接入 |
| 性能优化 | P1 | 3d | 🔴 | 未开始 |
| 安全加固 | P0 | 3d | 🟡 | 凭证加密已落地；CORS/输入校验/敏感日志待审计 |
| 后端集成测试补全 | P0 | 2d | 🔴 | `tests/integration/` 为空 |
| qa/ 黑盒集成测试 | P0 | 2d | 🔴 | 部署后环境接口测试待建立 |
| 压力测试 | P0 | 2d | 🔴 | 100 并发目标 |
| 上线检查清单 | P1 | 1d | 🔴 | 待编制 |

### 阶段 6

| 任务 | 优先级 | 建议工时 | 状态 | 说明 |
|------|--------|----------|------|------|
| 小程序框架搭建 | P1 | 2d | ⏸️ | Taro 4 + React |
| 微信登录 | P1 | 2d | ⏸️ | 复用后端 JWT |
| 首页 / 行情页 / 集合竞价可视化 | P1 | 9d | ⏸️ | ec-canvas 渲染 |
| AI 分析页 / 个人中心 | P2 | 4d | ⏸️ | 复用后端接口 |
| 测试与包体积优化 | P2 | 2d | ⏸️ | 目标 < 2MB |

## 5. 里程碑

| 里程碑 | 时间 | 判定标准 |
|--------|------|----------|
| M1：工程骨架可用 | 第 2 周末 | `cd backend && uv sync && uv run uvicorn app.main:app --reload` 启动成功；`cd web && npm install && npm run dev` 启动成功；`uv run ruff check .` 无错误。 |
| M2：数据管道跑通 | 第 6 周末 | `docker compose up postgres redis minio -d` 后，`uv run pytest -m collector` 通过；行情/新闻采集任务运行后 `collector_log` 有成功记录；幂等写入重复执行不报错。 |
| M3：后端 API 可用 | 第 9 周末 | `uv run pytest -m unit` 全部通过；Swagger `/docs` 中 P0 接口可调用并返回符合 `shared/` 类型的响应；5 个核心 Skill 回归样例全部命中 JSON Schema。 |
| M4：Web 端可用 | 第 13 周末 | `npm run build` 成功；Lighthouse 首屏 < 3s；Playwright E2E `login → dashboard → chain → stock` 通过。 |
| M5：后台与 MCP 可用 | 第 16 周末 | 管理员可通过 `/admin` 完成用户/股票/研报/新闻/任务 CRUD；MCP Server `/api/v1/mcp/tools` 返回 9 Tools，`/api/v1/mcp/invoke` 调用成功率 ≥ 95%。 |
| M6：Web 生产上线（V1.0 MVP） | 第 20 周末 | 生产环境可访问；采集任务稳定运行 3 个交易日；系统可用性 ≥ 99.5%；通过安全审查；`qa/` 黑盒测试通过率 ≥ 95%。 |
| M7：小程序可用（V1.1） | 第 24 周末 | 微信开发者工具可预览；集合竞价曲线正确渲染；包体积 < 2MB。 |

## 6. 关键成功指标

| 指标 | 目标 | 当前状态 |
|------|------|----------|
| V1.0 MVP 交付周期（Web 生产上线） | ≤ 20 周 | 进行中 |
| 后端 API 接口覆盖率 | 100% 覆盖需求文档 P0/P1 功能 | P0 接口主体完成 |
| 数据采集成功率 | 交易日关键任务 ≥ 95% | 待采集监控统计 |
| Web 首屏加载 | < 3 秒 | 待测量 |
| AI Skill 可调用率 | 5 个核心 Skill 全部可通过 API 返回有效结构化结果 | 产业链 Skill 已通，其余待回归 |
| 后端 Service 层测试覆盖率 | ≥ 70% | 待测量 |
| 后端 API 层测试覆盖率 | ≥ 60% | 待测量 |
| 前端 Utils/Hooks 测试覆盖率 | ≥ 60% | 待测量 |
| E2E 核心链路覆盖 | 登录 → 仪表盘 → 产业链 → 个股 100% | 未建立 |
| qa/ 黑盒集成测试通过率 | ≥ 95% | 未建立 |
| 小程序包体积（V1.1） | < 2 MB | 未启动 |

> **建议**：在阶段 5 前引入 `pytest-cov` 与 Vitest coverage 跑一轮基线，把上表“当前状态”从定性改为定量。

## 7. 主要风险与应对

| 风险 | 等级 | 状态 | 应对措施 |
|------|------|------|----------|
| 数据源接口变更或反爬升级 | 高 | 持续 | 多源故障切换、本地缓存、监控告警、采集器与 pipeline 解耦 |
| AI Skill 输出格式不稳定 | 高 | 持续 | 明确 JSON Schema、Pydantic 校验、格式修复兜底、回归样例库 |
| 数据质量差导致 AI 结果不可用 | 高 | 持续 | 数据校验规则、异常数据人工确认队列、来源引用与置信度标注 |
| 前后端接口契约频繁变更 | 中 | 已缓解 | `shared/` 目录作为法律依据、mock API、每周契约对齐 |
| 中间件资源占用超出预算 | 中 | 持续 | 开发环境按需启停、ES/Milvus 内存调优、必要时降级为可选 |
| 小程序审核不通过或包体积超标 | 中 | 未开始 | 代码压缩、按需引入、CDN 资源、避免敏感文案、预留审核缓冲 |
| 数据采集合规性 | 高 | 已缓解 | 遵守 robots.txt、仅采集公开数据、保留日志；已使用公开 API 与标准 User-Agent |
| 平台输出被误认为投资建议 | 中 | 持续 | 显著免责声明、不出现买卖建议、用户协议明确 |
| SCF 冷启动或超时 | 中 | 已缓解 | 预置并发、合理超时、AI 分析异步化、P99 监控；已引入 Redis 队列 + worker 模式替代纯 SCF 长任务 |
| 生产密钥 / API-KEY 泄露 | 中 | 持续 | 环境变量/密钥管理、AES-256-GCM 加密、日志过滤、撤销机制；凭证加密工具已落地 |

## 8. 资源需求建议

| 角色 | 人数 | 主要职责 |
|------|------|----------|
| 后端工程师 | 1-2 | FastAPI、采集器、数据库、Skill 集成、MCP Server |
| 前端工程师 | 1 | React Web 端、后台管理 |
| 小程序工程师 | 0 → 1（V1.1） | Taro 小程序（可由前端兼任），V1.0 阶段不投入 |
| DevOps / 部署 | 0.5 | Docker、SCF、CI/CD、监控、生产安全加固 |
| 产品/测试 | 0.5 | 原型验收、测试用例、上线检查 |

## 9. 风险跟踪机制

- **每日站会**：同步阻塞问题。
- **每周风险登记册 review**：技术负责人更新风险状态。
- **每阶段末里程碑评审**：Go / No-Go 决策。
- **上线前检查**：全团队执行上线检查清单。

## 10. 当前优先事项与下一步

基于代码库实际进度，V1.0 MVP 的剩余瓶颈按优先级排序如下：

1. **MCP Server 完整实现**（P0）
   - 补齐 9 Tools + 2 Resources，接入 SSE 传输，提供客户端配置模板。
   - 文件：`backend/app/api/v1/mcp/server.py`

2. **API-KEY 生命周期管理**（P0）
   - 确认后端接口与数据库模型是否完整，补齐创建/撤销/校验流程。

3. **测试与覆盖率基线**（P0）
   - 运行 `uv run pytest --cov` 与 `npm run test:coverage`（如已配置），把第 6 节指标量化。
   - 补齐 `tests/integration/` 与 E2E 测试骨架。

4. **生产加固**（P1，阶段 5 前置）
   - 域名 HTTPS、CLS 日志、监控告警、压力测试、安全审查。

5. **Makefile 与 README 同步**（P2）
   - 完善一键启动命令，降低新成员上手成本。

> **Go/No-Go 建议**：在阶段 5 大规模投入前，先完成 MCP Server 与 API-KEY 管理，并跑通一轮集成测试；否则生产上线后外部工具接入将成为明显缺口。
