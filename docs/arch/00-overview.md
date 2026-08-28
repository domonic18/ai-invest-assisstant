# 智能投研数据平台 — 总体架构设计

## 1. 项目定位

面向投资分析场景的**数据采集 → 清洗入库 → 智能分析 → 可视化展示**全链路平台，
以 Web 端为核心，覆盖每日复盘、产业链分析、个股研究、资金流向、集合竞价、研报与财报中心等场景。

- **数据源**：巨潮资讯(cninfo)、同花顺(10jqka)、东方财富、新浪财经、Tushare、上交所/深交所
- **采集内容**：行情(K 线/分时/竞价)、财务报表、涨停/跌停池、板块资金流、研报与财报 PDF、公告与新闻、市场宽度、宏观指标
- **AI 能力**：产业链分析、研报/财报摘要、涨停归因、每日 AI 大盘综述（YAML 声明式分区、可模块级编辑）
- **输出形式**：响应式 Web 前端（桌面 + 移动端底部导航）
- **部署方式**：腾讯云函数 SCF（Web 函数 + Job 函数）+ 腾讯云轻量服务器（中间件）

## 2. 部署架构全景图

```
┌────────────────────────────────────────────────────────────────────────────┐
│                              腾讯云 部署全景                                 │
│                                                                             │
│  ┌─────────────────────────────┐   ┌──────────────────────────────────────┐ │
│  │ 腾讯云 SCF Web 函数          │   │ 腾讯云 SCF Job 函数 (异步采集)        │ │
│  │                             │   │                                      │ │
│  │ ┌─────────────────────────┐ │   │  ┌──────┐ ┌──────┐ ┌──────┐ ┌────┐ │ │
│  │ │  Docker 镜像 (前后端合一) │ │   │  │K线采集│ │财报采集│ │新闻采集│ │研报│ │ │
│  │ │                         │ │   │  │Job   │ │Job   │ │Job   │ │Job │ │ │
│  │ │  Nginx :9000            │ │   │  └──┬───┘ └──┬───┘ └──┬───┘ └──┬─┘ │ │
│  │ │  ├── / → React 静态资源  │ │   │     │ Timer 触发器按需触发           │ │
│  │ │  ├── /api/* → FastAPI   │ │   │     └──────────┬──────────┬─────┘   │ │
│  │ │  └── /ws/* → WebSocket  │ │   │        写入 PG/ES/MinIO/Milvus      │ │
│  │ └─────────────────────────┘ │   │        （或常驻 worker 从 Redis 队列拉取）│ │
│  │                             │   │                                      │ │
│  │  ←── 浏览器 (Web 桌面/移动) │   └──────────────────────────────────────┘ │
│  └─────────────────────────────┘                                            │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │              腾讯云轻量应用服务器 (4核16GB + 500GB 数据盘)             │  │
│  │                                                                       │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────┐ ┌────────────────────┐  │  │
│  │  │PostgreSQL│ │  Redis   │ │Elasticsearch │ │     MinIO          │  │  │
│  │  │+Timescale│ │  缓存/队列│ │  全文检索     │ │  PDF文件/对象存储   │  │  │
│  │  │:5432     │ │  :6379   │ │  :9200       │ │  :9000             │  │  │
│  │  └──────────┘ └──────────┘ └──────────────┘ └────────────────────┘  │  │
│  │                         ┌──────────────────┐                        │  │
│  │                         │ Milvus 向量知识库  │                        │  │
│  │                         │ :19530            │                        │  │
│  │                         └──────────────────┘                        │  │
│  │                                                                       │  │
│  │              所有服务通过 Docker Compose 统一编排管理                  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

> Web 与采集共享同一套 `backend/` 代码：`app/` 是 FastAPI Web 服务，`collector/` 是采集 runtime，按场景选择 SCF Job（一次性触发，CLI 入口 `collector.runtime.cli`）或常驻 worker（从 Redis 队列拉取，入口 `collector.runtime.worker`）。

## 3. 系统逻辑架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户层 (User Layer)                              │
│                                                                              │
│  ┌──────────────────────────────┐    ┌──────────────────────────────┐       │
│  │   Web 桌面端 (浏览器)         │    │   Web 移动端 (响应式 + Tab Bar)│       │
│  │  每日复盘 │ 产业链 │ 个股      │    │  复盘 │ 分析 │ 设置           │       │
│  │  资金流向 │ 集合竞价 │ 研报     │    │  AI 助手底部弹层               │       │
│  │  财报中心 │ 后台管理            │    │                              │       │
│  │  React + ECharts + G6 + D3   │    │                              │       │
│  └──────────────┬───────────────┘    └──────────────┬───────────────┘       │
│                 │                                   │                        │
│                              HTTPS (API 网关)                                │
│                 │                                   │                        │
└─────────────────┴───────────────────────────────────┴────────────────────────┘
                  │                                   │
┌─────────────────┴───────────────────────────────────┴────────────────────────┐
│                    腾讯云 SCF — Web 函数 (Docker 镜像)                         │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │            Nginx (:9000) + FastAPI (:8000)  ← 同一容器内               │   │
│  │  JWT 鉴权 │ 路由 │ 静态资源（hash 长缓存 / SPA 入口禁缓存）            │   │
│  │  / → React 静态资源    /api/* → FastAPI（LLM 接口代理超时 300s）       │   │
│  │  /docs /openapi.json /health                                          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└───────┬──────────────────────────────────────────────────────────────────────┘
        │
┌───────┴──────────────────────────────────────────────────────────────────────┐
│              腾讯云 SCF — Job 函数 / 常驻 worker (异步采集)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                        │
│  │行情采集Job│ │财报采集Job│ │新闻采集Job│ │研报采集Job│  Timer 触发器或        │
│  └─────┬────┘ └─────┬────┘ └─────┬────┘ └─────┬────┘  Redis 队列调度          │
│        └─────────────┴───────────┴─────────────┘                              │
│                          │                                                    │
│      collector runtime：core / runtime / spiders / stores                    │
│      多渠道优先级 + 失败自动 fallback，runner 是 collector_log 唯一写入口      │
└──────────────────────────┬────────────────────────────────────────────────────┘
                           │
┌──────────────────────────┴────────────────────────────────────────────────────┐
│                    腾讯云轻量服务器 — 数据存储层 (Docker Compose)               │
│  ┌──────────┐ ┌──────────┐ ┌──────────────┐ ┌────────────────────────┐       │
│  │PostgreSQL│ │  Redis   │ │Elasticsearch │ │ MinIO + Milvus         │       │
│  │ 结构化数据│ │ 缓存/队列 │ │  全文检索    │ │ PDF存储 / 向量知识库   │       │
│  └──────────┘ └──────────┘ └──────────────┘ └────────────────────────┘       │
└───────────────────────────────────────────────────────────────────────────────┘
```

## 4. 技术选型总览

| 层次 | 技术 | 部署位置 | 选型理由 |
|------|------|----------|----------|
| **Web 前端** | React 18 + Vite + TypeScript | SCF Web 函数（Docker 镜像内 Nginx 静态资源） | 现代前端框架，生态完善 |
| **后端 API** | FastAPI (Python 3.10+) + SQLAlchemy 2.0 | SCF Web 函数（Docker 镜像内 Supervisor 守护） | 异步高性能、类型安全 |
| **数据采集** | 自研 collector runtime + httpx + akshare（仅部分数据源） | SCF Job 函数 / 常驻 worker | 声明式 TaskSpec 注册表 + 多渠道 fallback |
| **可视化** | ECharts + AntV/G6 v5 + D3.js | 前端打包至镜像 | 产业链图谱(G6)、K线/竞价(ECharts)、板块河流/排名(D3/ECharts) |
| **结构化存储** | PostgreSQL + TimescaleDB | 轻量服务器 Docker | 时序行情数据高效存储 |
| **搜索引擎** | Elasticsearch | 轻量服务器 Docker | 公告/新闻全文检索 |
| **文件存储** | MinIO (S3 兼容) | 轻量服务器 Docker | PDF 财报/研报对象存储，预签名 URL 下发 |
| **向量知识库** | Milvus Standalone | 轻量服务器 Docker | PDF 文档向量化，Agent RAG 检索 |
| **缓存/队列** | Redis | 轻量服务器 Docker | 热数据缓存、Session、采集任务队列 |
| **AI Agent** | PydanticAI + YAML Prompts + Skills + MCP | SCF Web 函数（通过 API 触发） | Python 原生 Agent SDK，OpenAI/Anthropic 双协议路由 |
| **认证** | JWT (OAuth2 表单) | FastAPI 模块 | 首个注册用户自动晋升管理员 |
| **容器化** | Docker + Docker Compose | SCF + 轻量服务器 | 环境统一，一键部署 |
| **CI/CD** | GitHub Actions → TCR | GitHub | 自动构建推送，VERSION 文件注入构建号 |

## 5. 项目目录结构

```
ai-invest-assisstant/
├── .github/
│   └── workflows/                      # GitHub Actions CI/CD
│       ├── ci.yml
│       └── build-and-push.yml
│
├── backend/                            # FastAPI 后端 + 采集模块
│   ├── app/                            # Web API 应用
│   │   ├── api/v1/                     # API 路由
│   │   │   ├── auth.py                 # OAuth2 登录/注册（首用户自动管理员）
│   │   │   ├── users.py                # 用户资料/自选股
│   │   │   ├── stocks.py               # 股票搜索/详情/板块归属
│   │   │   ├── kline.py                # K 线数据
│   │   │   ├── auction.py              # 集合竞价 + 指数竞价成交额趋势
│   │   │   ├── fund_flow.py            # 资金流向 + 板块资金流趋势
│   │   │   ├── market.py               # 大盘综述/AI 复盘/涨停复盘/补采
│   │   │   ├── chain.py                # 产业链版本化分析
│   │   │   ├── research.py             # 研报筛选/PDF/AI 摘要
│   │   │   ├── financial_report.py     # 财报中心：列表/采集/AI 摘要
│   │   │   ├── financial.py            # 财务体检 + 历史趋势
│   │   │   ├── hotspot.py              # 热点追踪
│   │   │   ├── admin/                  # 后台管理接口
│   │   │   │   ├── users.py / stocks.py / reports.py / news.py
│   │   │   │   ├── tasks.py / system.py
│   │   │   │   ├── llm_config.py
│   │   │   │   ├── collector.py / collector_channels.py / collector_data_types.py
│   │   │   └── mcp/                    # MCP Server 接口
│   │   │       └── server.py
│   │   ├── agent/                      # AI Agent 运行时
│   │   │   ├── core/                   # prompt_loader / skill_loader / llm_router / mcp_client / prompt_renderer
│   │   │   ├── skills/                 # 已实现：industry_chain_analysis（产业链）
│   │   │   ├── tools/                  # db_tools 等内部工具
│   │   │   └── router.py               # Supervisor 路由
│   │   ├── prompts/                    # 提示词配置（YAML）
│   │   │   ├── agents/                 # supervisor / chain / research / hotspot / financial analyst
│   │   │   └── skills/                 # industry-chain / research-report-summary / financial-report-summary /
│   │   │                               #   financial-health-check / hotspot-detection / chain-breakthrough /
│   │   │                               #   market-daily-review / limit-up-review
│   │   ├── core/                       # 配置、安全、连接、异常
│   │   │   ├── config.py / security.py / database.py / redis.py / logging.py / exceptions.py
│   │   ├── models/                     # SQLAlchemy ORM：命名遵循 <分类>_<数据类型>_<标的> 约定
│   │   ├── schemas/                    # Pydantic 数据模型
│   │   ├── repositories/               # 仓储层（查询构造与执行，禁止管理事务）
│   │   │                               #   按业务子域分组：admin/ chain/ market/ reports/ review/ user/
│   │   ├── services/                   # 业务逻辑层（事务边界、AI 调用、采集编排）
│   │   │                               #   按业务子域分组：admin/ assistant/ chain/ collector/ common/
│   │   │                               #   market/ reports/ review/ user/（根目录仅 __init__ 聚合）
│   │   ├── utils/                      # crypto 等公共工具
│   │   ├── dependencies/               # get_db 等依赖注入
│   │   └── main.py                     # 应用入口
│   ├── collector/                      # 采集 runtime
│   │   ├── core/                       # 基础设施：base(PostgresCollector/共享 engine) / http_client / parsing /
│   │   │                               #   pipelines / exporters / locks / calendar / logging / config
│   │   ├── runtime/                    # 执行层：runner(统一执行器) / registry(TaskSpec 声明表) / resolver /
│   │   │                               #   channels / queue / dispatcher / scheduler / worker / cli / scf_handler
│   │   ├── spiders/                    # 各数据源采集器（声明表配置 + collect/transform）
│   │   │                               #   含 *_base.py 共享基类（kline_base / auction_base / sector_fund_flow_base）
│   │   └── stores/                     # 重存储编排（financial_report_store / research_report_store）
│   ├── tests/                          # 测试
│   │   ├── unit/ / integration/
│   ├── pyproject.toml                  # uv 依赖与工具配置
│   └── uv.lock                         # 依赖锁定文件
│
├── web/                                # React Web 前端
│   ├── src/
│   │   ├── api/                        # API 客户端
│   │   ├── components/
│   │   │   ├── layout/                 # Header / Sidebar / Layout / MobileTabBar
│   │   │   ├── charts/                 # KlineChart / IndexKlineChart / IntradayChart / IntradaySpark /
│   │   │   │                           #   ChainGraph / FinancialTrendCharts / StockChartView / useKlineKeyboardNav
│   │   │   ├── common/                 # Brand / MarkdownText / SourceNote
│   │   │   └── auth/                   # ProtectedLayout / ProtectedAdmin / RedirectIfAuthenticated
│   │   ├── hooks/                      # 自定义 Hooks（TanStack Query 包装）
│   │   ├── pages/                      # 页面
│   │   │   ├── Dashboard/              # 每日复盘：指数 K 线 / 行情统计 / 板块 / 涨停复盘 / AI 综述 / 自选股
│   │   │   ├── ChainAnalysis/          # 产业链版本化分析（G6 图谱 + 版本切换）
│   │   │   ├── StockDetail/            # 同花顺风格多周期 K 线 + 财务 tab（含历史趋势）
│   │   │   ├── CapitalFlow/            # 板块河流图 + 排名图（含概念板块）
│   │   │   ├── AuctionReview/          # 集合竞价指数成交额趋势
│   │   │   ├── Research/               # 研报筛选 / PDF 下载 / AI 摘要
│   │   │   ├── FinancialReport/        # 财报中心：采集 + 列表 + AI 摘要
│   │   │   ├── Financial/              # 财务体检详情
│   │   │   ├── Hotspot/
│   │   │   ├── Settings/               # 基本信息 / 配色方案 / K 线均线 / 安全
│   │   │   ├── Login/ Register/
│   │   │   └── Admin/                  # 总览 + Users/Stocks/Reports/News/Tasks/LLMConfig/Collector/CollectorChannelConfig
│   │   ├── stores/                     # Zustand 状态（auth / colorScheme / userSettings）
│   │   ├── test/                       # 测试环境初始化与 mocks
│   │   ├── types/ utils/ constants/ config/
│   │   ├── App.tsx / main.tsx / router.tsx
│   ├── e2e/                            # Playwright E2E 测试
│   ├── index.html
│   ├── package.json
│   └── ... 构建配置（vite / vitest / playwright / tsconfig）
│
├── shared/                             # 前后端共享类型与常量（独立 npm 包）
│   ├── api/
│   │   ├── endpoints.ts                # API 端点常量
│   │   └── index.ts
│   ├── types/
│   │   ├── stock.ts / chain.ts / market.ts / admin.ts / api.ts / user.ts
│   └── utils/
│   └── package.json
│
├── docker/                             # 容器与编排配置
│   ├── web/                            # Web 函数镜像（前后端合一）
│   │   ├── Dockerfile
│   │   ├── nginx.conf                  # /assets/ 长缓存 / /api/ 代理超时 300s
│   │   └── supervisord.conf            # 守护 Nginx + FastAPI
│   ├── collector/                      # 采集镜像（CLI 单任务 或 常驻 worker）
│   │   ├── Dockerfile
│   │   └── entrypoint-collector.sh     # COLLECT_TASK 单任务，否则启动 worker
│   └── database/
│       ├── init-scripts/               # 01-schema / 02-indexes / 03-seed / 04-milvus-collections
│       └── migrations/                 # 增量迁移 SQL（按日期归档）
│
├── docs/                               # 项目文档
│   ├── arch/                           # 架构设计
│   ├── plan/                           # 开发计划
│   ├── prototypes/                     # HTML 原型
│   └── requirement/                    # 需求文档
│
├── skills/                             # Skill 业务描述（SKILL.md）
│   ├── industry-chain-analysis/
│   ├── research-summary/
│   ├── financial-health-check/
│   ├── hotspot-detection/
│   └── chain-breakthrough/
│
├── qa/                                 # 黑盒集成/QA 测试（独立 uv 项目）
│   ├── conftest.py                     # fixtures、环境变量、资源清理
│   ├── pyproject.toml
│   └── integration/
│       ├── test_auth.py / test_collector.py / test_health.py
│
├── scripts/                            # 本地与部署脚本
│   ├── setup-local.sh / build-images.sh / deploy-scf.sh
│   ├── run-collector.sh / run-scheduler.sh
│
├── .dockerignore                       # Docker 构建忽略规则
├── .env.example                        # 环境变量模板
├── .gitignore
├── VERSION                             # 版本号（CI 注入构建号）
├── docker-compose.yml                  # 全栈本地/生产编排
├── docker-compose-dev.yml              # 开发环境编排
├── docker-compose.infra.yml            # 轻量服务器基础设施编排
├── Makefile                            # 常用命令
├── LICENSE
└── README.md
```

### 目录设计原则

1. **后端与采集解耦**：`backend/app/` 负责 Web API，`backend/collector/` 负责 SCF Job / worker 采集，两者可独立打包镜像但共享 ORM 与仓储层。
2. **共享契约中心化**：`shared/` 作为独立 npm 包，被 Web 与后端共同引用，避免接口契约漂移。
3. **前端按页面组织**：`web/src/pages/` 按业务模块划分（每日复盘 / 产业链 / 个股 / 资金流 / 竞价 / 研报 / 财报 / 财务 / 热点 / 设置 / 后台），组件、Hooks、状态管理各自独立。
4. **测试分层独立**：白盒测试贴近代码（`backend/tests/`、`web/src/test/`），黑盒 QA 测试独立成册（`qa/`），便于不同环境执行。
5. **文档与代码分离**：`docs/` 仅存放设计文档与原型，不混入工程代码。
6. **Skill 与提示词热更新**：`skills/` 以 Markdown 形式维护业务逻辑，`backend/app/prompts/` 以 YAML 形式维护 LLM 提示词，无需修改代码即可调整 AI 分析行为。
7. **Agent 运行时与业务解耦**：`backend/app/agent/` 只负责 Agent 执行引擎，具体能力由 `prompts/` 和 `skills/` 驱动。
8. **仓储层与事务边界**：`app/repositories/` 只构造查询，`app/services/` 拥有事务边界（显式 commit），路由层禁止直接操作数据库。

## 6. 核心数据流

```
                    ┌──────────────────┐
                    │  腾讯云 SCF Job    │
                    │  Timer 触发器     │
                    │  定时触发采集任务   │
                    └────────┬─────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
   ┌──────────┐      ┌──────────────┐      ┌──────────┐
   │ 行情采集  │      │ 财报/研报采集 │      │ 新闻采集  │
   │ (Job)    │      │ (Job)        │      │ (Job)    │
   └────┬─────┘      └──────┬───────┘      └────┬─────┘
        │                   │                   │
        ▼                   ▼                   ▼
   ┌────────────────────────────────────────────────┐
   │           数据清洗管道 (Pipeline)                │
   │        去重 → 标准化 → 校验 → 脱敏              │
   └──────────────────────┬─────────────────────────┘
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
        ┌─────────┐ ┌──────────┐ ┌────────┐
        │PostgreSQL│ │  MinIO   │ │   ES   │
        │+Milvus  │ │ PDF/研报 │ │新闻索引│
        └────┬─────┘ └────┬─────┘ └───┬────┘
             │            │            │
             └────────────┼────────────┘
                          │              ← 轻量服务器（数据存储）
         ═════════════════╪══════════════
                          │              ← SCF Web 函数（计算 + 展示）
                          │
              ┌───────────┴───────────┐
              │    AI Agent 分析引擎   │
              │ (PydanticAI + MCP + Skills) │
              │                       │
              │  ┌─────────────────┐  │
              │  │ 财报分析 Skill   │  │
              │  ├─────────────────┤  │
              │  │ 研报摘要 Skill   │  │
              │  ├─────────────────┤  │
              │  │ 热点追踪 Skill   │  │
              │  ├─────────────────┤  │
              │  │ 财务体检 Skill   │  │
              │  ├─────────────────┤  │
              │  │ 突破点追踪 Skill │  │
              │  └─────────────────┘  │
              └───────────┬───────────┘
                          │
          ┌───────────────┴───────────────┐
          │                               │
   ┌──────┴──────┐               ┌────────┴────────┐
   │  Web 前端    │               │  微信小程序       │
   │  可视化展示   │               │  移动端数据查看    │
   └─────────────┘               └─────────────────┘
```

## 7. 功能矩阵

| 功能模块 | 桌面 Web | 移动 Web | 实现要点 |
|----------|----------|----------|----------|
| 每日复盘 | ✅ 完整 | ✅ 卡片 | 指数 K 线 / 涨停复盘 / AI 大盘综述（可模块级编辑）/ 自选股行情卡 |
| 产业链分析 | ✅ 完整交互 | ✅ 双指缩放 | G6 图谱 + 版本切换 + AI 助手确认；基于经营范围自下而上推导环节 |
| 个股详情 | ✅ 多周期 K 线 | ✅ 单图 | 同花顺风格多窗口预设（日/周/月）+ 财务 tab 历史趋势 + 板块归属 |
| 集合竞价 | ✅ 指数成交额趋势 | ✅ | 指数竞价口径走 Tushare `stk_auction` 聚合 |
| 资金流向 | ✅ 板块河流图 + 排名 | ✅ | 行业板块走东财 / 概念板块钉死同花顺；流入红/流出绿配色 |
| 财务体检 | ✅ 完整报告 + 历史趋势 | ❌ | 个股详情 Tab，含毛利率/净利率/ROE 等近 8 期趋势 |
| 研报中心 | ✅ 筛选 + PDF + AI 摘要 | ❌ | 券商/行业/评级多维筛选；PDF 用 curl_cffi 绕 WAF |
| 财报中心 | ✅ 列表 + 采集 + AI 摘要 | ❌ | 后台触发采集，file_metadata.summary 缓存 AI 摘要 |
| 热点追踪 | ✅ | ✅ 速览 | 话题云、新闻时间线、热点传导链 |
| AI 分析报告 | ✅ 完整 | ✅ 精简 | YAML 声明式分区，产业链/涨停复盘/每日综述各有独立 prompt |
| 自选股管理 | ✅ | ✅ | 个股详情页一键加入/移除 |
| 用户设置 | ✅ 完整 | ✅ 基础 | 涨跌配色方案（红涨绿跌 / 绿涨红跌）+ 个人 K 线均线 |
| 后台管理 | ✅ 9 个子页 | ❌ | 用户/股票/研报/资讯/任务/LLM 配置/采集渠道/数据类型优先级 |

## 8. 后续文档索引

- [01-data-source.md](./01-data-source.md) — 数据源详细分析与采集策略
- [02-data-collection.md](./02-data-collection.md) — 采集引擎架构与云函数 Job 定时调度
- [03-data-storage.md](./03-data-storage.md) — 数据库设计与存储方案
- [04-ai-agent.md](./04-ai-agent.md) — AI Agent 体系设计（Python Agent SDK + YAML 提示词）
- [05-web-frontend.md](./05-web-frontend.md) — Web 前端 + 小程序架构设计
- [06-deployment.md](./06-deployment.md) — 腾讯云部署方案（SCF + 轻量服务器）
- [07-testing.md](./07-testing.md) — 测试体系设计（单元/集成/E2E/QA）
