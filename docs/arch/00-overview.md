# 智能投研数据平台 — 总体架构设计

## 1. 项目定位

面向投资分析场景的**数据采集 → 清洗入库 → 智能分析 → 可视化展示**全链路平台，
以 Web 端为核心，覆盖工作台、每日复盘、产业链分析、个股研究、资金流向、集合竞价、投资日历、研报与财报中心等场景。

- **数据源**：巨潮资讯(cninfo)、同花顺(10jqka)、东方财富、新浪财经、Tushare、上交所/深交所、财联社
- **采集内容**：行情(K 线/分时/竞价)、财务报表、涨停/跌停池、板块资金流、研报与财报 PDF、公告与新闻（含财联社电报准实时快讯）、市场宽度、宏观指标、投资日历事件、全球跟踪指标（黄金/美债收益率/美元指数）
- **AI 能力**：产业链分析、研报/财报摘要、涨停归因、每日 AI 大盘综述（YAML 声明式分区、可模块级编辑）、自选股 AI 每日分析（盘面解读/操作策略/止损线）
- **输出形式**：响应式 Web 前端（桌面 + 移动端底部导航）+ AI 助手对话面板
- **部署方式**：SCF Web 函数（SPA + API 同源一体镜像）+ 轻量服务器（数据与采集任务）+ COS（文件），详见 [06-deployment.md](./06-deployment.md)

## 2. 部署架构全景图

```
┌────────────────────────────────────────┐
│ 用户浏览器（桌面 / 移动 · 响应式单端） │
└────────────────────────────────────────┘
                     │ HTTPS（SPA + /api/* 同源）
                     ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ SCF Web 函数 — web-api 一体镜像（:9000）                                     │
│ React SPA + FastAPI 单 uvicorn 进程（SPA 静态托管）· SSE 流式输出            │
│ deepagents 助手对话进程内承载 · 预置并发保冷启动 · 执行上限 900s              │
└──────────────────────────────────────────────────────────────────────────────┘
                        │ 公网直连（读写 PG/Redis）                       │ S3 协议
                        ▼                                        ▼
┌────────────────────────────────────────────┐   ┌──────────────────────────────┐
│ 轻量应用服务器 2C4G（ap-beijing）          │   │ COS 对象存储                 │
│ 数据层 postgres/timescale · redis · es     │   │ 研报/财报 PDF · 知识库文件   │
│ 任务层 celery-beat + 双 worker             │   │ pg_dump 定时备份目标         │
│   （realtime+batch 合并 · heavy 并发=1）   │   └──────────────────────────────┘
│   采集爬虫 + LLM 归因                      │
│   （>900s / WAF 固定出口，永久驻留）       │
│     ─▶ 东财 / 新浪 / 巨潮 / tushare        │
└────────────────────────────────────────────┘
```

- **接入层**：SCF Web 函数自定义域名 invest.17aitech.com（已备案），SPA 与 API 同源一体（单 uvicorn 进程一体镜像 :9000），助手对话进程内承载
- **API 层**：SCF Web 函数（FastAPI 一体镜像），SSE 流式输出；长任务（>900s）与需固定出口 IP 的采集爬虫留置轻量服务器执行
- **数据与任务层**：轻量服务器承载 postgres/timescale、redis、elasticsearch 与 Celery 采集调度（`collector_task` 表为调度真相源）
- **文件存储**：COS（S3 兼容端点），兼作 pg_dump 定时备份目标
- **镜像发布**：GitHub Actions 构建推送 TCR，服务器/SCF 拉取部署；现状问题与演进路径见 [../plan/deployment-evolution-plan.md](../plan/deployment-evolution-plan.md)

> Web 与采集共享同一套 `backend/` 代码：`app/` 是 FastAPI Web 服务，`collector/` 是采集 runtime，通过 Celery 队列（realtime/batch/heavy）执行，亦保留 CLI 单任务入口 `collector.runtime.cli` 与 SCF 事件适配 `collector.runtime.scf_handler`。

## 3. 系统逻辑架构

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│ 用户层 (User Layer)                                                                │
│ 工作台 / 复盘 / 产业链 / 个股 / 资金流 / 集合竞价 / 日历 / 研报 / 财报 / 后台管理  │
│ 移动 Web：响应式 + 底部 Tab Bar · AI 助手对话面板                                  │
└────────────────────────────────────────────────────────────────────────────────────┘
                                         HTTPS
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────┐
│ API 层 (FastAPI · uvicorn :9000)                                                   │
│ JWT 鉴权 │ REST 路由 │ SSE 流式输出（AI 助手）│ /health /docs │ MCP Server         │
│ auth/users/stocks/kline/auction/fund_flow/market/chain/research/                   │
│ financial_report/financial/hotspot/calendar/assistant/admin                        │
└────────────────────────────────────────────────────────────────────────────────────┘
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────┐
│ 应用服务层 (app/services · 事务边界)                                               │
│ 业务子域服务：admin/assistant/chain/collector/market/reports/review/user           │
│ AI Agent 运行时：deepagents 助手 + PydanticAI Skills + YAML Prompts                │
│ llm_router 双协议路由 · repositories 只构造查询（禁止管理事务）                    │
└────────────────────────────────────────────────────────────────────────────────────┘
                                     投递采集任务│
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────┐
│ 采集执行层 (collector runtime)                                                     │
│ celery-beat（collector_task 表同步调度）→ 双 worker（realtime+batch / heavy）      │
│ 准实时：stream 驻留进程（财联社电报 10s 增量轮询，非 beat 调度）                   │
│ runner 统一执行（collector_log 唯一写入口）· registry 33 任务 TaskSpec             │
│ 多渠道优先级 + FAILED 自动 fallback · 日期参数默认 latest_trading_day              │
└────────────────────────────────────────────────────────────────────────────────────┘
                                         读写│
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────┐
│ 数据层                                                                             │
│ PostgreSQL/Timescale（结构化 + 时序）│ Redis（缓存 / broker / 分布式锁）           │
│ Elasticsearch（全文检索）│ COS（研报/财报 PDF · 知识库文件）                       │
└────────────────────────────────────────────────────────────────────────────────────┘
```

## 4. 技术选型总览

| 层次 | 技术 | 部署位置 | 选型理由 |
|------|------|----------|----------|
| **Web 前端** | React 18 + Vite + TypeScript | SCF web-api 一体镜像（FastAPI 静态托管同源） | 现代前端框架，生态完善 |
| **后端 API** | FastAPI (Python 3.10+) + SQLAlchemy 2.0 | SCF Web 函数（单 uvicorn 进程一体镜像） | 异步高性能、类型安全 |
| **AI 助手运行时** | deepagents（LangChain Agent Protocol）+ assistant-ui | SCF web-api 进程内 | 流式对话/工具调用，会话持久化 `assistant_session` |
| **数据采集** | 自研 collector runtime + Celery + httpx/akshare/curl_cffi | 轻量服务器 Celery 双 worker（realtime+batch / heavy 并发=1） | 声明式 TaskSpec 注册表（33 任务）+ 多渠道 fallback |
| **可视化** | ECharts + AntV/G6 v5 + D3.js | 前端打包至 web-api 镜像 | 产业链图谱(G6)、K线/竞价(ECharts)、板块河流/排名(D3/ECharts) |
| **结构化存储** | PostgreSQL + TimescaleDB | 轻量服务器 Docker | 时序行情数据高效存储 |
| **搜索引擎** | Elasticsearch | 轻量服务器 Docker | 公告/新闻全文检索 + 知识库 |
| **文件存储** | COS (S3 兼容) | 腾讯云 COS | PDF 财报/研报对象存储，兼作 pg_dump 备份目标 |
| **缓存/队列** | Redis | 轻量服务器 Docker | 热数据缓存、Session、Celery broker、分布式锁 |
| **AI Agent** | PydanticAI + YAML Prompts + Skills + MCP | web-api 进程内 | Python 原生 Agent SDK，OpenAI/Anthropic 双协议路由 |
| **认证** | JWT (OAuth2 表单) | FastAPI 模块 | 首个注册用户自动晋升管理员 |
| **容器化** | Docker + Docker Compose | 轻量服务器 | 环境统一，一键部署 |
| **CI/CD** | GitHub Actions → TCR | GitHub | 自动构建推送，服务器/SCF 仅 pull 部署 |

## 5. 项目目录结构

```
ai-invest-assisstant/
├── .github/
│   └── workflows/
│       └── ci.yml                      # GitHub Actions CI/CD（构建 → TCR）
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
│   │   │   ├── assistant/              # AI 助手协议接口（threads / runs / skills / page_context）
│   │   │   └── mcp/                    # MCP Server 接口
│   │   │       └── server.py
│   │   ├── agent/                      # AI Agent 运行时
│   │   │   ├── core/                   # llm_router / prompt_loader / prompt_renderer / skill_loader
│   │   │   ├── runtime/                # deepagents 助手运行时：assistant_agent / assistant_tools / model_factory / wire
│   │   │   ├── skills/                 # 已实现：industry_chain_analysis（产业链）
│   │   │   └── tools/                  # db / chain / market / news / report / stock 内部工具
│   │   ├── prompts/                    # 提示词配置（YAML）
│   │   │   ├── agents/                 # supervisor / assistant / chain / research / hotspot / financial analyst
│   │   │   └── skills/                 # industry-chain-analysis / research-report-summary / financial-report-summary /
│   │   │                               #   financial-health-check / hotspot-detection / chain-breakthrough /
│   │   │                               #   market-daily-review / limit-up-review / watchlist-daily-analysis / research-summary
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
│   │   ├── celery_app.py               # Celery 应用（timezone=Asia/Shanghai，3 队列）
│   │   ├── celery_beat.py              # CollectorDatabaseScheduler（collector_task 表为调度真相源）
│   │   ├── celery_tasks.py             # 任务投递与 ReviewInputDataNotReady 重试封装
│   │   ├── core/                       # 基础设施：base(PostgresCollector/共享 engine) / http_client / parsing /
│   │   │                               #   pipelines / exporters / calendar / logging / config
│   │   ├── runtime/                    # 执行层：runner(统一执行器) / registry(TaskSpec 声明表) / resolver /
│   │   │                               #   channels / dispatcher / cli / scf_handler
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
│   │   │   ├── assistant/              # assistant-ui 助手面板：Provider / Thread / Composer / 会话侧栏
│   │   │   ├── common/                 # Brand / MarkdownText / SourceNote
│   │   │   └── auth/                   # ProtectedLayout / ProtectedAdmin / RedirectIfAuthenticated
│   │   ├── hooks/                      # 自定义 Hooks（TanStack Query 包装）
│   │   ├── pages/                      # 页面
│   │   │   ├── Dashboard/              # 每日复盘：指数 K 线 / 行情统计 / 板块 / 涨停复盘 / AI 综述 / 自选股
│   │   │   ├── Workbench/              # 工作台聚合页（登录默认入口：日历摘要 / 复盘结论 / 要闻 / 自选股概览 / 市场快览）
│   │   │   ├── Calendar/               # 投资日历（月历 / 周历 / 事件列表）
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
│   │   │   └── Admin/                  # 总览 + Users/Stocks/Reports/News/Tasks/LLMConfig/Collector/CollectorChannelConfig/TrackedIndex
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
│   ├── web/                            # Web 镜像（前后端合一，单 uvicorn 进程）
│   │   └── Dockerfile                  # SPA 静态托管 + API 同源 :9000（无代理层）
│   ├── collector/                      # 采集镜像（CLI 单任务 或 Celery beat/worker）
│   │   ├── Dockerfile
│   │   └── entrypoint-collector.sh     # COLLECT_TASK 单任务；COLLECTOR_MODE=beat/worker
│   └── database/
│       ├── init-scripts/               # 01-schema / 02-indexes / 03-seed
│       └── migrations/                 # 增量迁移 SQL（按日期归档，幂等可重复执行）
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
├── scripts/                            # 本地与构建脚本
│   └── setup-local.sh / build-images.sh
│
├── .dockerignore                       # Docker 构建忽略规则
├── .env.example                        # 环境变量模板
├── .gitignore
├── VERSION                             # 版本号（CI 注入构建号）
├── docker-compose.yml                  # 全栈编排（本地/生产共用）
├── docker-compose.prod.yml             # 生产叠加（端口/环境变量/资源限制）
├── Makefile                            # 常用命令
├── LICENSE
└── README.md
```

### 目录设计原则

1. **后端与采集解耦**：`backend/app/` 负责 Web API，`backend/collector/` 负责 Celery 采集调度与执行，两者独立打包镜像但共享 ORM 与仓储层。
2. **共享契约中心化**：`shared/` 作为独立 npm 包，被 Web 与后端共同引用，避免接口契约漂移。
3. **前端按页面组织**：`web/src/pages/` 按业务模块划分（工作台 / 每日复盘 / 产业链 / 个股 / 资金流 / 竞价 / 日历 / 研报 / 财报 / 财务 / 热点 / 设置 / 后台），组件、Hooks、状态管理各自独立。
4. **测试分层独立**：白盒测试贴近代码（`backend/tests/`、`web/src/test/`），黑盒 QA 测试独立成册（`qa/`），便于不同环境执行。
5. **文档与代码分离**：`docs/` 仅存放设计文档与原型，不混入工程代码。
6. **Skill 与提示词热更新**：`skills/` 以 Markdown 形式维护业务逻辑，`backend/app/prompts/` 以 YAML 形式维护 LLM 提示词，无需修改代码即可调整 AI 分析行为。
7. **Agent 运行时与业务解耦**：`backend/app/agent/` 只负责 Agent 执行引擎，具体能力由 `prompts/` 和 `skills/` 驱动。
8. **仓储层与事务边界**：`app/repositories/` 只构造查询，`app/services/` 拥有事务边界（显式 commit），路由层禁止直接操作数据库。

## 6. 核心数据流

```
┌────────────────────────────────────────────────────────────────────────────┐
│ 外部数据源：东方财富 / 新浪财经 / 巨潮资讯 / tushare / 交易所 / 财联社     │
└────────────────────────────────────────────────────────────────────────────┘
                                     拉取│
                                       ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ 采集执行层（Celery worker · realtime/batch/heavy）                         │
│ registry TaskSpec 声明（33 任务）· 多渠道优先级 · FAILED fallback          │
│ 限流/反爬：curl_cffi 指纹 · push2delay 镜像 · 重试退避                     │
└────────────────────────────────────────────────────────────────────────────┘
                                     清洗│
                                       ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ 数据清洗管道（collector.core.parsing / pipelines）                         │
│ parsing → transform → validate（required_fields 校验）                     │
└────────────────────────────────────────────────────────────────────────────┘
                                     入库│
                                       ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ 数据存储                                                                   │
│ PostgreSQL/Timescale：行情 / 股池 / 资金流 / 财务 / 全球指标 /             │
│ 日历事件 / 调度元数据                                                      │
│ Elasticsearch：新闻与公告全文索引 · COS：研报/财报 PDF 文件                │
└────────────────────────────────────────────────────────────────────────────┘
                                     查询│
                                       ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ API 层（FastAPI）                                                          │
│ 查询聚合 · Redis 缓存 · SSE 流式 · MCP Server 对外暴露                     │
└────────────────────────────────────────────────────────────────────────────┘
                                   数据供给│
                                       ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ AI 分析引擎（YAML Skills + PydanticAI / deepagents）                       │
│ 每日复盘综述 · 涨停归因 · 自选股每日分析 · 产业链分析 · 研报/财报摘要      │
│ 财务体检 · 热点检测 · 突破点追踪 · AI 助手对话                             │
└────────────────────────────────────────────────────────────────────────────┘
                                     展示│
                                       ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ 前端可视化（React SPA · SCF web-api 同源托管）                             │
│ 工作台 / 复盘 / 产业链 / 个股 / 资金流 / 竞价 / 日历 / 研报 / 财报 / 后台  │
└────────────────────────────────────────────────────────────────────────────┘
```

> AI 分析结果按 `input_hash = sha256(skill_id + 业务键)` 缓存于 `ai_analysis_result` 表，
> 定时任务（交易日 15:05 复盘综述、16:30 涨停归因、盘后自选股批量分析）与手动触发共享幂等缓存。


## 7. 功能矩阵

| 功能模块 | 桌面 Web | 移动 Web | 实现要点 |
|----------|----------|----------|----------|
| 工作台 | ✅ 登录默认页 | ❌ | 卡片化聚合：日历摘要 / 复盘结论 / 要闻 / 自选股概览 / 市场快览；模块可折叠、空态兜底 |
| 每日复盘 | ✅ 完整 | ✅ 卡片 | 指数 K 线 / 涨停复盘（含 AI 归因）/ AI 大盘综述（可模块级编辑）/ 自选股行情卡 |
| 产业链分析 | ✅ 完整交互 | ✅ 双指缩放 | G6 图谱 + 版本切换 + AI 助手确认；基于经营范围自下而上推导环节 |
| 个股详情 | ✅ 多周期 K 线 | ✅ 单图 | 同花顺风格多窗口预设（日/周/月）+ 财务 tab 历史趋势 + 板块归属 |
| 集合竞价 | ✅ 指数成交额趋势 | ✅ | 指数竞价口径走 Tushare `stk_auction` 聚合 |
| 资金流向 | ✅ 板块河流图 + 排名 | ✅ | 行业板块走东财 / 概念板块钉死同花顺；流入红/流出绿配色 |
| 财务体检 | ✅ 完整报告 + 历史趋势 | ❌ | 个股详情 Tab，含毛利率/净利率/ROE 等近 8 期趋势 |
| 研报中心 | ✅ 筛选 + PDF + AI 摘要 | ❌ | 券商/行业/评级多维筛选；PDF 用 curl_cffi 绕 WAF |
| 财报中心 | ✅ 列表 + 采集 + AI 摘要 | ❌ | 后台触发采集，file_metadata.summary 缓存 AI 摘要 |
| 热点追踪 | ✅ | ✅ 速览 | 话题云、新闻时间线、热点传导链 |
| 投资日历 | ✅ 月历/周历/列表 | ❌ | `calendar_event`：财联社日历 + FOMC/BLS 固定日程，`source_hash` 幂等去重，分类筛选 |
| AI 分析报告 | ✅ 完整 | ✅ 精简 | YAML 声明式分区，产业链/涨停归因/每日综述/自选股每日分析各有独立 prompt |
| AI 助手 | ✅ 对话面板 | ✅ 底部弹层 | assistant-ui + deepagents，流式 SSE、工具调用折叠、会话持久化 |
| 自选股管理 | ✅ | ✅ | 分组增删改查（`watchlist_group`，未分组归默认分组）+ AI 复盘分组开关，个股详情一键加入/移除 |
| 自选股 AI 每日分析 | ✅ 个股 Tab + 列表卡片 | ❌ | 盘后定时批量（heavy 队列），仅遍历开启复盘开关的分组；三段式输出（盘面解读/操作策略/止损线），`input_hash` 幂等缓存 |
| 跟踪指数 | ✅ 大盘页/工作台动态清单 | ✅ | `tracked_index_config` 全局配置 + `quote_global_index_daily`（黄金/美债收益率/美元指数），后台维护 |
| 用户设置 | ✅ 完整 | ✅ 基础 | 涨跌配色方案（红涨绿跌 / 绿涨红跌）+ 个人 K 线均线 |
| 后台管理 | ✅ 10 个子页 | ❌ | 用户/股票/研报/资讯/任务/LLM 配置/采集渠道/跟踪指数/采集任务（目录驱动） |

## 8. 后续文档索引

- [01-data-source.md](./01-data-source.md) — 数据源清单、反爬策略与存储去向
- [02-data-collection.md](./02-data-collection.md) — 采集引擎架构与 Celery 调度
- [03-data-storage.md](./03-data-storage.md) — 数据库设计与存储方案
- [04-ai-agent.md](./04-ai-agent.md) — AI Agent 体系设计（deepagents + YAML 提示词）
- [05-web-frontend.md](./05-web-frontend.md) — Web 前端架构设计
- [06-deployment.md](./06-deployment.md) — 部署架构与运维实操
- [07-testing.md](./07-testing.md) — 测试体系设计（单元/集成/E2E/QA）
