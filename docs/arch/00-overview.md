# 智能投研数据平台 — 总体架构设计

## 1. 项目定位

面向投资分析场景的**数据采集 → 清洗入库 → 智能分析 → 可视化展示**全链路平台，
提供 **Web 端 + 微信小程序** 双端访问能力。

- **数据源**：巨潮资讯(cninfo)、同花顺(10jqka)、东方财富、新浪财经等
- **采集内容**：交易行情、财报文件(PDF)、研报文件(PDF)、上市公司公告与新闻
- **AI 能力**：基于 Agent 的产业链分析、研报摘要、热点追踪、集合竞价分析
- **输出形式**：Web 前端可视化 + 微信小程序（移动端数据查看）
- **部署方式**：腾讯云函数 SCF（前后端）+ 腾讯云轻量服务器（中间件）

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
│  │ │  └── /ws/* → WebSocket  │ │   │                │          │         │ │
│  │ └─────────────────────────┘ │   │        写入 PG/ES/MinIO/Milvus      │ │
│  │                             │   │                                      │ │
│  │  ←── 浏览器 (Web端)         │   └──────────────────────────────────────┘ │
│  │  ←── 微信小程序             │                                            │
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

## 3. 系统逻辑架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户层 (User Layer)                              │
│                                                                              │
│  ┌──────────────────────────────┐    ┌──────────────────────────────┐       │
│  │      Web 端 (浏览器)          │    │     微信小程序 (移动端)        │       │
│  │  全功能投资分析平台            │    │  集合竞价 │ 行情 │ AI 速览    │       │
│  │  产业链图谱 │ K线 │ 研报 │ 热点│    │  Taro + React + ec-canvas     │       │
│  │  React + ECharts + G6 + D3   │    │                              │       │
│  └──────────────┬───────────────┘    └──────────────┬───────────────┘       │
│                 │                                   │                        │
│            HTTPS (API 网关)                    wx.request (HTTPS)             │
│                 │                                   │                        │
└─────────────────┴───────────────────────────────────┴────────────────────────┘
                  │                                   │
┌─────────────────┴───────────────────────────────────┴────────────────────────┐
│                    腾讯云 SCF — Web 函数 (Docker 镜像)                         │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │            Nginx (:9000) + FastAPI (:8000)  ← 同一容器内               │   │
│  │          JWT 鉴权 │ 路由 │ 静态资源 │ WebSocket 推送                   │   │
│  │    / → React 静态资源    /api/* → FastAPI    /ws/* → WebSocket        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└───────┬──────────────────────┬───────────────────────────────────────────────┘
        │                      │
┌───────┴──────────────────────┴───────────────────────────────────────────────┐
│                    腾讯云 SCF — Job 函数 (异步采集)                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                        │
│  │行情采集Job│ │财报采集Job│ │新闻采集Job│ │研报采集Job│  Timer 触发器驱动       │
│  └─────┬────┘ └─────┬────┘ └─────┬────┘ └─────┬────┘                        │
│        └─────────────┴───────────┴─────────────┘                              │
│                          │                                                    │
│              数据清洗管道 (去重→标准化→校验)                                   │
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
| **微信小程序** | Taro 4 + React + ec-canvas | 微信平台 | 复用 Web 端代码，ECharts 绑图 |
| **后端 API** | FastAPI (Python 3.11+) | SCF Web 函数（Docker 镜像内 Supervisor 守护） | 异步高性能、原生 WebSocket |
| **数据采集** | Scrapy + akshare + Playwright | SCF Job 函数（Timer 触发） | 异步执行，按需伸缩，无需常驻 |
| **可视化 (Web)** | ECharts + AntV/G6 + D3.js | 前端打包至镜像 | 产业链图谱(G6)、K线(ECharts)、资金流向(D3) |
| **可视化 (小程序)** | ECharts ec-canvas | 小程序组件 | 集合竞价曲线、K线缩略图 |
| **结构化存储** | PostgreSQL + TimescaleDB | 轻量服务器 Docker | 时序行情数据高效存储 |
| **搜索引擎** | Elasticsearch | 轻量服务器 Docker | 公告/新闻全文检索 |
| **文件存储** | MinIO (S3 兼容) | 轻量服务器 Docker | PDF 财报/研报对象存储 |
| **向量知识库** | Milvus Standalone | 轻量服务器 Docker | PDF 文档向量化，Agent RAG 检索 |
| **缓存/队列** | Redis | 轻量服务器 Docker | 热数据缓存、Session 管理 |
| **AI Agent** | PydanticAI / OpenAI Agents SDK + MCP + Skills | SCF Web 函数（通过 API 触发） | Python 原生 Agent SDK，类型安全，支持多 LLM |
| **认证** | JWT + 微信登录 | FastAPI 模块 | Web 端账号登录 + 小程序 wx.login |
| **容器化** | Docker + Docker Compose | SCF + 轻量服务器 | 环境统一，一键部署 |
| **CI/CD** | GitHub Actions → TCR | GitHub | 自动构建推送，云函数更新 |

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
│   │   │   ├── auth.py                 # 注册/登录/微信登录
│   │   │   ├── users.py                # 用户资料/自选股
│   │   │   ├── stocks.py               # 股票搜索与基础数据
│   │   │   ├── kline.py                # K 线数据
│   │   │   ├── auction.py              # 集合竞价数据
│   │   │   ├── fund_flow.py            # 资金流向
│   │   │   ├── chain.py                # 产业链分析
│   │   │   ├── research.py             # 研报摘要
│   │   │   ├── hotspot.py              # 热点追踪
│   │   │   ├── financial.py            # 财务体检
│   │   │   ├── admin/                  # 后台管理接口
│   │   │   │   ├── users.py
│   │   │   │   ├── stocks.py
│   │   │   │   ├── reports.py
│   │   │   │   ├── news.py
│   │   │   │   ├── tasks.py
│   │   │   │   └── system.py
│   │   │   └── mcp/                    # MCP Server 接口
│   │   │       └── server.py
│   │   ├── agent/                      # AI Agent 运行时
│   │   │   ├── core/                   # 核心引擎
│   │   │   │   ├── prompt_loader.py    # YAML 提示词加载
│   │   │   │   ├── skill_loader.py     # SKILL.md 加载
│   │   │   │   ├── llm_router.py       # 多模型路由
│   │   │   │   └── mcp_client.py       # MCP 工具客户端
│   │   │   ├── skills/                 # Skill 与 Agent 绑定
│   │   │   ├── tools/                  # 内部工具实现
│   │   │   └── router.py               # Supervisor 路由
│   │   ├── prompts/                    # 提示词配置（YAML）
│   │   │   ├── agents/                 # Agent 角色提示词
│   │   │   │   ├── supervisor.yaml
│   │   │   │   ├── chain_analyst.yaml
│   │   │   │   ├── research_analyst.yaml
│   │   │   │   ├── hotspot_analyst.yaml
│   │   │   │   └── financial_analyst.yaml
│   │   │   └── skills/                 # Skill 执行提示词
│   │   │       ├── industry-chain-analysis.yaml
│   │   │       ├── research-summary.yaml
│   │   │       ├── hotspot-detection.yaml
│   │   │       ├── financial-health-check.yaml
│   │   │       └── chain-breakthrough.yaml
│   │   ├── core/                       # 配置、安全、连接、异常
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   ├── database.py
│   │   │   ├── redis.py
│   │   │   ├── logging.py
│   │   │   └── exceptions.py
│   │   ├── models/                     # SQLAlchemy ORM 模型
│   │   ├── schemas/                    # Pydantic 数据模型
│   │   ├── services/                   # 业务逻辑层
│   │   ├── dependencies/               # FastAPI 依赖注入
│   │   └── main.py                     # 应用入口
│   ├── collector/                      # SCF Job 采集模块
│   │   ├── base.py                     # BaseCollector 抽象
│   │   ├── tasks.py                    # 采集任务路由
│   │   ├── spiders/                    # 各数据源采集器
│   │   │   ├── cninfo.py
│   │   │   ├── ths.py
│   │   │   ├── eastmoney.py
│   │   │   └── sina.py
│   │   ├── pipelines.py                # 数据清洗管道
│   │   ├── middleware.py               # 代理/Cookie/限速
│   │   ├── exporters.py                # PG/ES/MinIO 写入
│   │   └── settings.py                 # 采集全局配置
│   ├── tests/                          # 测试
│   │   ├── unit/
│   │   └── integration/
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── pytest.ini
│
├── web/                                # React Web 前端
│   ├── public/
│   ├── src/
│   │   ├── api/                        # API 客户端
│   │   ├── components/                 # 组件
│   │   │   ├── layout/                 # Header/Sidebar/Layout
│   │   │   ├── charts/                 # KlineChart/ChainGraph/SankeyChart
│   │   │   ├── common/                 # StockSelector/DateRangePicker
│   │   │   └── auth/                   # LoginForm/RegisterForm
│   │   ├── hooks/                      # 自定义 Hooks
│   │   ├── pages/                      # 页面
│   │   │   ├── Dashboard/
│   │   │   ├── ChainAnalysis/
│   │   │   ├── StockDetail/
│   │   │   ├── Hotspot/
│   │   │   ├── CapitalFlow/
│   │   │   ├── AuctionReview/
│   │   │   ├── Research/
│   │   │   ├── Settings/
│   │   │   ├── Login/
│   │   │   ├── Register/
│   │   │   └── Admin/
│   │   ├── stores/                     # Zustand 状态
│   │   ├── test/                       # 测试环境初始化与 mocks
│   │   ├── types/                      # 本地类型扩展
│   │   ├── utils/                      # 工具函数
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── router.tsx
│   ├── e2e/                            # Playwright E2E 测试
│   ├── index.html
│   ├── package.json
│   ├── playwright.config.ts
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── vitest.config.ts
│   └── .env.example
│
├── miniapp/                            # Taro 微信小程序
│   ├── config/
│   │   └── index.ts
│   ├── src/
│   │   ├── pages/                      # 小程序页面
│   │   │   ├── index/                  # 首页
│   │   │   ├── market/                 # 行情/自选股
│   │   │   ├── auction/                # 集合竞价可视化
│   │   │   ├── ai/                     # AI 分析速览
│   │   │   └── profile/                # 个人中心
│   │   ├── components/                 # 小程序组件
│   │   │   ├── ec-canvas/              # ECharts 小程序封装
│   │   │   ├── AuctionChart/
│   │   │   ├── StockCard/
│   │   │   └── HotNewsCard/
│   │   ├── hooks/
│   │   ├── utils/
│   │   ├── app.config.ts
│   │   ├── app.tsx
│   │   └── app.scss
│   ├── project.config.json
│   ├── package.json
│   └── tsconfig.json
│
├── shared/                             # Web + 小程序共享代码
│   ├── api/
│   │   ├── types.ts                    # API 响应类型
│   │   └── endpoints.ts                # API 端点常量
│   ├── types/
│   │   ├── stock.ts
│   │   ├── chain.ts
│   │   ├── auction.ts
│   │   ├── research.ts
│   │   └── user.ts
│   └── utils/
│       ├── formatters.ts
│       └── constants.ts
│
├── docker/                             # 容器与编排配置
│   ├── web/                            # Web 函数镜像（前后端合一）
│   │   ├── Dockerfile
│   │   ├── nginx.conf                  # 单镜像内 Nginx 配置
│   │   └── supervisord.conf            # 守护 Nginx + FastAPI
│   ├── collector/                      # SCF Job 采集镜像
│   │   ├── Dockerfile
│   │   └── entrypoint-collector.sh     # SCF Job 入口脚本
│   └── database/                       # 数据库初始化
│       └── init-scripts/
│           ├── 01-schema.sql
│           ├── 02-indexes.sql
│           ├── 03-seed.sql
│           └── 04-milvus-collections.py
│
├── docs/                               # 项目文档
│   ├── arch/                           # 架构设计
│   ├── plan/                           # 开发计划
│   ├── prototypes/                     # HTML 原型
│   └── requirement/                    # 需求文档
│
├── skills/                             # Skill 定义文件（Markdown + Schema）
│   ├── industry-chain-analysis/
│   ├── research-summary/
│   ├── hotspot-detection/
│   ├── financial-health-check/
│   └── chain-breakthrough/
│
├── qa/                                 # 黑盒集成/QA 测试
│   ├── conftest.py                     # fixtures、环境变量、资源清理
│   ├── requirements.txt
│   └── integration/
│       ├── test_auth.py
│       ├── test_stocks.py
│       ├── test_chain.py
│       └── test_mcp.py
│
├── scripts/                            # 本地与部署脚本
│   ├── setup-local.sh
│   ├── build-images.sh
│   └── deploy-scf.sh
│
├── .dockerignore                       # Docker 构建忽略规则
├── .env.example                        # 环境变量模板
├── .gitignore
├── docker-compose.yml                  # 全栈本地/生产编排
├── docker-compose-dev.yml              # 开发环境编排
├── docker-compose.infra.yml            # 轻量服务器基础设施编排
├── Makefile                            # 常用命令
├── LICENSE
└── README.md
```

### 目录设计原则

1. **后端与采集解耦**：`backend/app/` 负责 Web API，`backend/collector/` 负责 SCF Job 采集，两者可独立打包镜像。
2. **共享契约中心化**：`shared/` 存放 API 类型与端点常量，被 Web、小程序、后端共同引用，避免接口契约漂移。
3. **前端按页面组织**：`web/src/pages/` 与 `miniapp/src/pages/` 按业务模块划分，组件、Hooks、状态管理各自独立。
4. **测试分层独立**：白盒测试贴近代码（`backend/tests/`、`web/src/test/`），黑盒 QA 测试独立成册（`qa/`），便于不同环境执行。
5. **文档与代码分离**：`docs/` 仅存放设计文档与原型，不混入工程代码。
6. **Skill 与提示词热更新**：`skills/` 以 Markdown 形式维护业务逻辑，`backend/app/prompts/` 以 YAML 形式维护 LLM 提示词，无需修改代码即可调整 AI 分析行为。
7. **Agent 运行时与业务解耦**：`backend/app/agent/` 只负责 Agent 执行引擎，具体能力由 `prompts/` 和 `skills/` 驱动。

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

## 7. 双端功能矩阵

| 功能模块 | Web 端 | 小程序端 | 说明 |
|----------|--------|----------|------|
| 大盘概览 | ✅ 仪表盘 | ✅ 首页卡片 | |
| 产业链图谱 | ✅ 完整交互 | ❌ | 移动端不适合复杂图谱操作 |
| 集合竞价可视化 | ✅ | ✅ 核心功能 | 小程序版 ec-canvas |
| K线分析 | ✅ 完整K线 | ✅ 缩略K线 | |
| 资金流向 | ✅ 桑基图 | ❌ | |
| 财务体检 | ✅ 完整报告 | ❌ | |
| 研报阅读 | ✅ 全文阅读 | ✅ 摘要速览 | |
| 热点追踪 | ✅ 完整页面 | ✅ 速报推送 | |
| 自选股管理 | ✅ | ✅ | |
| AI 分析报告 | ✅ 完整报告 | ✅ 精简摘要 | |
| 产业链突破点 | ✅ 完整页面 | ✅ 速报卡片 | |
| 用户设置 | ✅ 完整 | ✅ 基础 | |

## 8. 后续文档索引

- [01-data-source.md](./01-data-source.md) — 数据源详细分析与采集策略
- [02-data-collection.md](./02-data-collection.md) — 采集引擎架构与云函数 Job 定时调度
- [03-data-storage.md](./03-data-storage.md) — 数据库设计与存储方案
- [04-ai-agent.md](./04-ai-agent.md) — AI Agent 体系设计（Python Agent SDK + YAML 提示词）
- [05-web-frontend.md](./05-web-frontend.md) — Web 前端 + 小程序架构设计
- [06-deployment.md](./06-deployment.md) — 腾讯云部署方案（SCF + 轻量服务器）
- [07-testing.md](./07-testing.md) — 测试体系设计（单元/集成/E2E/QA）
