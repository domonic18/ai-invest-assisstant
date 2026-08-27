# AI Invest Assistant 代码库重构方案

## 1. 背景与目标

### 1.1 背景

项目经过多轮迭代后，代码量与业务模块快速增长，已出现以下结构性问题：

- 部分源文件超过 350 行，单一模块承担过多职责；
- 前后端存在重复工具函数与业务逻辑；
- **常量与场景定义分散在多处**，状态值、业务枚举、超时时间、Query Key、颜色值等未集中管理；
- 根目录下存在 4 个 `docker-compose*.yml` 文件，命名与用途不一致；
- `docs/` 中缺少开源项目标准的贡献指南、变更日志、安全策略等；
- 测试目录结构分散，集成测试目录为空；
- Skill 与 Prompt 存在双轨维护风险。

### 1.2 目标

按照开源项目的可维护性、可测试性、可扩展性标准，对代码目录结构、模块划分、配置文件进行系统重构，使：

- 单一文件职责明确，尽量控制在 350 行以内；
- 目录结构清晰反映业务边界；
- **常量、枚举、场景定义集中管理，前后端统一引用**；
- Docker Compose 配置一套易懂、可组合；
- 文档完整，便于新贡献者上手；
- 测试覆盖结构与业务模块对齐。

### 1.3 重构原则

1. **单一职责**：一个文件/模块只做一件事；
2. **按业务域组织**：后端 `services/`、`api/` 按业务子域分组；前端 `pages/` 按页面拆分为 `components/`；
3. **消除重复**：前后端共用逻辑下沉到 `shared/`；
4. **常量集中**：业务枚举、状态值、超时、颜色、Key 等统一放到 `constants/` 或 `shared/constants/`，禁止魔法字符串；
5. **显式优于隐式**：Compose 文件命名与用途一一对应；
6. **渐进式重构**：按优先级分阶段实施，避免一次性大爆炸式改动；
7. **不破坏现有 API**：所有重构在接口层保持向后兼容。

---

## 2. 现状盘点

### 2.1 项目顶层结构

```
.
├── backend/              # Python FastAPI + AI Agent + Collector
├── web/                  # React + TypeScript 前端
├── shared/               # 前后端共享类型与工具
├── skills/               # 人类可读的 Skill 定义（Markdown）
├── docker/               # Dockerfile、Caddy、数据库初始化/迁移脚本
├── docs/                 # 架构文档、计划、需求、原型
├── qa/                   # Python 集成测试（独立 pyproject.toml）
├── scripts/              # 本地开发脚本
├── docker-compose*.yml   # 4 个 Compose 文件
├── Makefile
├── CLAUDE.md
└── README.md
```

### 2.2 文件长度分布（Top 30）

| 文件 | 行数 | 所属域 |
|---|---|---|
| `backend/tests/unit/collector/test_spiders.py` | 1,842 | 测试 |
| `backend/tests/unit/services/test_market_service.py` | 1,204 | 测试 |
| `shared/types/api.ts` | 785 | 共享类型 |
| `backend/app/services/market_review_service.py` | 463 | 后端服务 |
| `web/src/components/charts/ChainGraph.tsx` | 496 | 前端组件 |
| `web/src/pages/StockDetail/StockDetail.tsx` | 653 | 前端页面 |
| `web/src/api/mappers.ts` | 611 | 前端 API |
| `backend/app/api/v1/assistant.py` | 369 | 后端 API |
| `backend/app/services/stock_service.py` | 373 | 后端服务 |
| `backend/app/services/chain_service.py` | 351 | 后端服务 |
| `backend/app/agent/runtime/assistant_tools.py` | 389 | Agent 工具 |

> 统计说明：仅统计 `.py`、`.ts`、`.tsx`、`.yaml`、`.yml` 文件，排除 `node_modules`、`.venv`、`dist`、缓存目录。

### 2.3 Docker Compose 现状

当前根目录存在 4 个 Compose 文件，与“本地开发”和“远程生产”两个主要场景不匹配：

| 文件 | 用途 | 问题 |
|---|---|---|
| `docker-compose.infra.yml` | 基础设施：Postgres/TimescaleDB、Redis、ES、MinIO、Milvus、etcd | 作为独立文件存在，本地/生产都需要它，增加组合复杂度 |
| `docker-compose.yml` | 应用基座：web + collector + 默认环境变量 | 与 `-dev` 文件大量重复定义 `web`/`collector` |
| `docker-compose-dev.yml` | 开发模式：web + collector + 本地 volume 挂载 | 使用连字符，命名风格不一致；不是真正的 override |
| `docker-compose.prod.yml` | 生产覆盖：关闭 web 端口、添加 Caddy | 必须与 `docker-compose.yml` + `infra` 组合使用 |

核心矛盾：两个主要场景（本地开发、远程生产）需要记忆不同的 `COMPOSE_FILE` 组合，且 `docker-compose.yml` 与 `docker-compose-dev.yml` 重复定义了应用服务。

### 2.5 常量 / 场景定义现状

项目中的业务枚举、状态值、超时时间、颜色值、Query Key 等常量**分散在业务代码中**，未形成统一的常量管理层。主要表现：

| 常量类别 | 分散位置示例 | 问题 |
|---|---|---|
| **业务状态** | `"success"` / `"failed"` / `"pending"` / `"running"` 在 `backend/app/models/*.py`、`backend/app/services/*.py`、`backend/collector/runtime/*.py` 中硬编码 | 缺少统一枚举，易拼写错误 |
| **用户角色** | `"admin"` / `"user"` / `"analyst"` 在 `backend/app/models/user.py`、`backend/app/schemas/user.py`、`backend/app/services/user_service.py`、`web/src/api/mappers.ts` 中重复出现 | 角色变更时需多处修改 |
| **财报类型** | `"annual"` / `"semi_annual"` / `"q1"` / `"q3"` 在 `backend/app/services/financial_report_service.py`、`web/src/pages/FinancialReport/FinancialReport.tsx`、`web/src/pages/FinancialReport/CollectModal.tsx` 中重复定义选项和中文标签 | 前后端标签可能不一致 |
| **产业链节点类型** | `"upstream"` / `"midstream"` / `"downstream"` 在 `shared/types/chain.ts`、`web/src/components/charts/ChainGraph.tsx`、`web/src/components/charts/ChainGraphToolbar.tsx` 中硬编码 | 缺少统一枚举与多语言标签 |
| **边关键性/壁垒** | `"high"` / `"medium"` / `"low"` 在 `web/src/components/charts/chainGraphStyle.ts`、后端 schema、测试中多处出现 | 语义未统一 |
| **超时与缓存时间** | `LIVE_STALE_TIME`、`LLM_GENERATION_TIMEOUT`、`POLL_INTERVAL` 等分散在 `web/src/hooks/*.ts`、`web/src/api/market.ts` | 难以全局调整 |
| **Query Key / Storage Key** | `MARKET_KEY`、`FINANCIAL_REPORT_KEY`、`STORAGE_KEY` 等分散在每个 hook 和组件中 | 命名空间冲突风险 |
| **颜色值** | `#14161c`、`#23262e`、`#6366f1` 等硬编码在 67 处以上 | 主题切换/维护困难 |
| **SKILL ID** | `"market-daily-review"`、`"limit-up-review"`、`"industry-chain-analysis"` 等硬编码在 `backend/app/services/*.py` | 缺少统一注册表 |

> 统计说明：颜色值硬编码出现 67 次以上（仅统计 `web/src/` 和 `shared/`）。



## 3. 问题诊断

### 3.1 后端（backend/app/）

#### 3.1.1 服务层文件过大且职责混杂

- `market_review_service.py`（463 行）：同时包含 AI 生成、缓存、哈希、持久化、用户编辑叠加、响应组装；
- `stock_service.py`（373 行）：同时处理行情快照、K 线、分钟线、集合竞价、资金流向；
- `financial_report_service.py`（318 行）：列表查询、采集触发、PDF AI 摘要混在一起；
- `collector_channel_config_service.py`（304 行）：管理后台配置服务放在 `services/` 根目录，未按子域分组。

#### 3.1.2 Admin 相关服务未分组

以下文件均属于管理后台，但散落在 `services/` 根目录：

- `admin_news_service.py`
- `admin_report_service.py`
- `admin_stock_service.py`
- `admin_task_service.py`
- `admin_user_service.py`
- `collector_channel_config_service.py`

#### 3.1.3 Agent 工具层存在双轨

- `agent/runtime/assistant_tools.py`：LangChain 工具封装，包含股票、新闻、财报、产业链、市场等；
- `agent/tools/db_tools.py`：底层数据库查询工具；
- 两者职责边界模糊，且 `assistant_tools.py` 自行创建 `AsyncSessionLocal`，绕过了 FastAPI 依赖注入的事务规则。

#### 3.1.4 重复逻辑

- 行业名称规范化：
  - `backend/app/agent/runtime/assistant_tools.py`
  - `backend/app/services/limit_pool_service.py`
  - `web/src/pages/ChainAnalysis/ChainAnalysis.tsx`
- 金额格式化：
  - `backend/app/services/market_review_service.py`
  - `backend/app/services/limit_up_ai_service.py`
  - `web/src/utils/formatters.ts`
- PDF/LLM 摘要流程：
  - `backend/app/services/research_service.py`
  - `backend/app/services/financial_report_service.py`

#### 3.1.5 API 路由文件过大

- `backend/app/api/v1/assistant.py`（369 行）：混合了 thread CRUD、run 流式接口、skill 列表、page-context 辅助函数。

### 3.2 前端（web/src/）

#### 3.2.1 页面组件内联子组件 / 职责过重

- `StockDetail.tsx`（653 行）：内联定义 `StockFinancial`、`StockResearch`、`StockHeader`、`ErrorState`；
- `FinancialReport.tsx`（317 行）：内联定义 `FinancialReportCard`，内联 `summarySnippet`、`formatFileSize` 等工具函数；
- `Research.tsx`（283 行）：内联定义 `ResearchCard`，内联 `summarySnippet`；
- `Settings.tsx`（236 行）：内联定义 `sortByPeriod`、`nextDefaultPeriod`、`nextDefaultColor` 等 MA 配置工具函数；
- `Financial.tsx`（169 行）：内联定义 `buildBalanceRows`、`buildIncomeRows`、`buildCashRows`、`renderPercent`；
- `Hotspot.tsx`（116 行）：内联定义 `formatAmount` 与表格 `columns`；
- `StockChartView.tsx`（597 行）：数据准备、ECharts option 构建、指标 UI 全部耦合；
- `FinancialTrendCharts.tsx`（247 行）：内联 `buildBaseOption` 与盈利能力/营收/偿债三大 option 对象；
- `AssistantPanel.tsx`（255 行）：内联 `TodoListBar` 子组件及 `clamp`、`readStoredWidth` 等工具函数；
- `AssistantRuntimeProvider.tsx`（148 行）：内联 `extractTodos`、`extractPageResultFromMessages`、`extractPageResult` 等运行时数据提取函数。

上述文件同时承担 UI 渲染、数据转换、工具函数三种职责，违反单一职责原则，也与已规范拆分的 `ChainAnalysis/`、`Dashboard/`、`components/assistant/` 不一致。

#### 3.2.2 API 层映射逻辑不统一

- `api/mappers.ts` 是全局 DTO 映射中心；
- `api/market.ts` 又内联了自己的 `mapIndexQuote`、`mapLimitUpData`；
- `api/index.ts` 统一再导出，但源码中仍直接导入 `@/api/market`。

#### 3.2.3 空目录与主题值重复

- `web/src/types/` 为空；
- 多个页面直接使用 Tailwind 十六进制色值，未复用 `theme/colors.ts`。

### 3.3 共享层（shared/）

- `shared/types/api.ts`（785 行）覆盖所有域的请求/响应类型，成为“大泥球”；
- `shared/utils/formatters.ts` 仅 11 行，未承载前后端重复的格式化逻辑；
- `shared/dist/` 不在 git 中，本地/CI 需手动 `npm run build`，新贡献者易踩坑。

### 3.4 Skill / Prompt 双轨

- 顶层 `skills/`：5 个 `SKILL.md`，人类可读；
- `backend/app/prompts/skills/`：9 个 YAML，运行时加载；
- 两者内容重叠，且 `limit-up-review`、`market-daily-review` 仅在 YAML 中存在。

### 3.5 测试

- `backend/tests/integration/` 只有 `__init__.py`，为空；
- `backend/tests/unit/collector/test_spiders.py`（1,842 行）和 `backend/tests/unit/services/test_market_service.py`（1,204 行）过大；
- `web/e2e/` 仅 2 个 Playwright 用例；
- `qa/` 目录与 `backend/tests/` 并行，职责边界不够清晰。

### 3.7 常量 / 场景定义分散问题

#### 3.7.1 魔法字符串泛滥

业务状态、角色、类型等字符串直接写在 SQL 过滤条件、Pydantic 校验、前端条件判断中。例如：

- `ChainAnalysisVersion.status == "success"`
- `user.role != "admin"`
- `ChainNode['type']` 使用字面量 `"upstream"` / `"midstream"` / `"downstream"`

这种方式在类型检查和 IDE 提示上较弱，且容易因拼写错误导致运行时问题。

#### 3.7.2 前后端常量不同步

- 财报类型选项在 `backend/app/services/financial_report_service.py` 和 `web/src/pages/FinancialReport/FinancialReport.tsx` 中分别维护；
- 角色校验在 `backend/app/schemas/user.py` 使用正则 `^(user|admin|analyst)$`，而前端 `web/src/api/mappers.ts` 只判断 `role === 'admin'`；
- 产业链节点类型在 `shared/types/chain.ts` 用 TypeScript 联合类型定义，但后端没有对应 Python Enum。

#### 3.7.3 主题/样式常量未收敛

- 67 处以上直接使用十六进制色值；
- `ChainGraph.tsx`、`StockChartView.tsx`、`FinancialTrendCharts.tsx` 各自重复定义图表背景色、网格色、文字色；
- 部分组件使用 `theme/colors.ts` 的 `panelColors`，部分直接写死。

#### 3.7.4 超时与缓存策略分散

- `LLM_GENERATION_TIMEOUT = 300_000` 写在 `web/src/api/market.ts`；
- `LIVE_STALE_TIME`、`LIVE_REFETCH_INTERVAL` 写在多个 `hooks/*.ts`；
- 后端 LLM 超时在 `backend/app/core/config.py` 集中配置，但前端没有统一配置层。

#### 3.7.5 Query Key / Storage Key 命名空间风险

- 每个 hook 自行定义 `QUERY_KEY`，如 `['market']`、`['research']`、`['financial-reports']`；
- `localStorage` key 如 `'color_scheme'`、`'assistant-sidebar-width'`、`'ai-invest.stock-detail.views'` 命名风格不一致；
- 缺少统一前缀规范，未来新增 key 容易冲突。



## 4. 重构方案

### 4.1 Docker Compose 重构

#### 目标

- 保持 Compose 文件在项目根目录；
- 只保留两个主要场景：本地开发全栈、远程生产部署全栈；
- 每个文件自包含，无需记忆 `COMPOSE_FILE` 组合；
- 本地开发命令最简，生产部署命令明确。

#### 推荐文件结构（位于根目录）

```
.
├── docker-compose.yml          # 本地开发全栈：infra + web + collector（含 dev volumes）
└── docker-compose.prod.yml     # 生产部署全栈：infra + web + collector + Caddy
```

#### 文件职责

| 文件 | 职责 | 使用场景 |
|---|---|---|
| `docker-compose.yml` | 本地开发全栈：基础设施（Postgres/TimescaleDB、Redis、ES、MinIO、Milvus、etcd）+ `web` + `collector`，启用 volume 挂载、`.env` 加载、宿主机端口映射 | 本地开发 `docker compose up -d` |
| `docker-compose.prod.yml` | 生产部署全栈：与本地相同的 infra + 应用服务，关闭 web 宿主机端口，添加 Caddy 反向代理，使用构建产物而非 volume 挂载 | 远程服务器 `docker compose -f docker-compose.prod.yml up -d --build` |

#### 移除的文件

- `docker-compose-dev.yml`：功能合并到 `docker-compose.yml`；
- `docker-compose.override.yml`：不再需要，本地开发由单一全栈文件承担；
- `docker-compose.infra.yml`：合并到两个全栈文件中，避免多文件组合。

#### 使用方式

**本地开发**

```bash
docker compose up -d
```

如需 rebuild：

```bash
docker compose up -d --build
```

**生产部署**

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

> 服务器 `.env` 中不再需要设置 `COMPOSE_FILE`，直接指定 `-f docker-compose.prod.yml` 即可。

#### 命名规范

统一使用 `docker-compose.<modifier>.yml` 形式：

- `docker-compose.yml`：本地开发全栈（无修饰符，Docker 默认加载）；
- `docker-compose.prod.yml`：生产部署全栈。

废弃 `docker-compose-dev.yml`（连字符风格），避免与点号风格混用。

#### 兼容性更新

迁移后需同步更新：

- `Makefile` 中的 `infra` / `up` / `prod` 目标：
  - `infra` 目标可改为 `docker compose up -d postgres redis elasticsearch minio milvus etcd`；
  - 新增 `prod` 目标：`docker compose -f docker-compose.prod.yml up -d --build`；
- `README.md`、`docs/arch/06-deployment.md`、`docs/ops/deployment.md` 中的启动命令；
- 服务器 `.env` 中移除 `COMPOSE_FILE` 变量；
- `.gitignore` 如已忽略 `docker-compose.override.yml` 可移除该规则。

---

### 4.2 后端分层架构重构

#### 4.2.1 分层原则

后端严格保持 **路由层（Router）→ 服务层（Service）→ 数据访问层（Repository）→ 模型层（Model）** 四层结构，与现有 `backend/CLAUDE.md` 一致：

- **`api/`**：只处理 HTTP 逻辑（参数校验、响应格式、状态码、异常转换），禁止直接操作数据库；
- **`services/`**：只承载业务逻辑、流程编排、跨域协调，所有写操作显式管理事务；
- **`repositories/`**：只负责查询构造与执行，禁止调用 `commit()` / `rollback()`；
- **`models/`**：只定义 ORM 模型与表结构。

**禁止把 Repository 放入 `services/` 子目录**，必须保持两层目录平行，按同一业务子域命名，便于一一对应。

#### 4.2.2 按业务子域组织服务层

```
backend/app/services/
├── __init__.py
├── market/                 # 行情相关
│   ├── __init__.py
│   ├── stock_service.py    # 原 stock_service 拆分为 quote/kline/intraday/auction/fund_flow
│   ├── kline_service.py
│   ├── auction_service.py
│   └── fund_flow_service.py
├── chain/
│   ├── __init__.py
│   ├── chain_service.py    # 版本/对比/持久化逻辑
│   └── chain_analysis_service.py  # analyze_and_persist 独立
├── reports/
│   ├── __init__.py
│   ├── research_service.py
│   └── financial_report_service.py
├── review/
│   ├── __init__.py
│   ├── market_review_service.py
│   └── limit_up_ai_service.py
├── admin/
│   ├── __init__.py
│   ├── admin_news_service.py
│   ├── admin_report_service.py
│   ├── admin_stock_service.py
│   ├── admin_task_service.py
│   ├── admin_user_service.py
│   └── collector_channel_config_service.py
├── collector/
│   └── ...
└── common/
    ├── __init__.py
    ├── formatters.py       # 金额/百分比格式化
    └── industry.py         # 行业名称规范化
```

服务层子模块只保留业务编排；每个服务通过对应 `repositories/<domain>/*.py` 完成数据访问，禁止在 `services/` 内直接写 `session.execute(...)`。

#### 4.2.3 按业务子域组织数据访问层

将现有扁平的 `repositories/` 目录按业务子域分组，与 `services/` 的域划分保持一致：

```
backend/app/repositories/
├── __init__.py
├── base.py                 # 通用 CRUD 基类 / 分页辅助
├── market/
│   ├── __init__.py
│   ├── stock_repository.py
│   ├── kline_repository.py
│   ├── auction_repository.py
│   └── fund_flow_repository.py
├── chain/
│   ├── __init__.py
│   ├── chain_version_repository.py
│   ├── chain_node_repository.py
│   └── chain_edge_repository.py
├── reports/
│   ├── __init__.py
│   ├── research_repository.py
│   └── financial_report_repository.py
├── review/
│   ├── __init__.py
│   ├── market_review_repository.py
│   └── limit_up_repository.py
├── admin/
│   ├── __init__.py
│   ├── admin_news_repository.py
│   ├── admin_report_repository.py
│   ├── admin_stock_repository.py
│   ├── admin_task_repository.py
│   ├── admin_user_repository.py
│   └── collector_channel_config_repository.py
└── user/
    ├── __init__.py
    ├── user_repository.py
    └── watchlist_repository.py
```

**原则**：

- Repository 只做 SQL/ORM 查询与单条/批量数据映射，不处理业务规则；
- 复杂查询按域拆分到对应 `repositories/<domain>/`；
- 跨域查询由 Service 协调多个 Repository，禁止 Repository 互相调用。

#### 4.2.4 拆分超大服务文件

**`market_review_service.py` → `review/` 子模块**

```
backend/app/services/review/
├── __init__.py
├── market_review_service.py      # 仅保留对外 facade / 事务边界
├── market_review_generator.py    # LLM 生成 + 缓存
└── market_review_formatter.py    # 响应组装
```

对应数据访问层：

```
backend/app/repositories/review/
├── __init__.py
└── market_review_repository.py   # 数据持久化/查询
```

**`stock_service.py` → `market/` 子模块**

- `stock_quote_service.py`：个股快照；
- `stock_kline_service.py`：日 K；
- `stock_intraday_service.py`：分钟线；
- `stock_auction_service.py`：集合竞价；
- `stock_fund_flow_service.py`：个股资金流向。

原 `stock_service.py` 可保留为 facade，委托给子模块，保持 API 兼容。

**`financial_report_service.py` → `reports/financial_report_service.py` + `reports/financial_report_summarizer.py`**

提取通用 `PdfSummarizer` 基类，供 `research_service.py` 复用。

#### 4.2.5 提取通用工具到 `shared/` 或 `common/`

- 行业规范化：放到 `backend/app/services/common/industry.py`；前端继续复用 `shared/utils/industry.ts`；
- 金额格式化：放到 `shared/utils/formatters.ts`（前后端同构）；后端通过 `shared` 包引用；
- PDF 摘要：抽象 `BasePdfSummarizer`。

#### 4.2.6 API 路由拆分

**`backend/app/api/v1/assistant.py` → `api/v1/assistant/` 包**

```
backend/app/api/v1/assistant/
├── __init__.py
├── router.py              # 聚合子路由
├── threads.py             # thread CRUD
├── runs.py                # run / stream / cancel
├── skills.py              # skill 列表
└── page_context.py        # page-context 辅助
```

`router.py` 使用 FastAPI `APIRouter` 组装，保持外部 URL 不变。路由层只负责调用 `services/` 对应方法，禁止直接调用 `repositories/` 或 `session.execute(...)`。

---

### 4.3 Agent 工具层重构

#### 目标

统一 `agent/tools/` 目录，按域拆分；明确工具与底层 db 查询的分层。

```
backend/app/agent/
├── core/                  # LLM 路由、Agent 构建
├── runtime/               # LangGraph 运行时代码
├── skills/                # Skill YAML 加载与执行
└── tools/
    ├── __init__.py
    ├── common.py          # 工具注册、session 注入辅助
    ├── market_tools.py    # 大盘、板块资金流、集合竞价
    ├── stock_tools.py     # 个股行情、K 线、财务
    ├── news_tools.py      # 新闻检索
    ├── report_tools.py    # 财报查询、下载、摘要
    ├── chain_tools.py     # 产业链查询与持久化
    └── db/
        ├── __init__.py
        └── query_tools.py # 原始 SQL/ORM 查询，供上层 tools 调用
```

#### 关键改动

- `assistant_tools.py` 中的工具按域拆入 `tools/*.py`；
- 每个工具函数接收 `session: AsyncSession` 参数，由 `runtime` 统一注入，而不是自行创建 `AsyncSessionLocal()`；
- `db_tools.py` 保留纯查询函数，不负责 LangChain `@tool` 装饰。

---

### 4.4 前端重构

#### 4.4.1 组件封装与页面目录组织原则

前端目录组织遵循 **“页面自治、组件复用、关注点分离”** 原则：

```
web/src/
├── api/              # API 客户端与请求函数（按域拆分）
├── components/       # 可复用 UI 组件（按业务/功能域拆分）
├── constants/        # 业务常量（前后端语义对齐）
├── hooks/            # 全局/跨页面复用的自定义 Hooks
├── pages/            # 页面级组件
│   └── PageName/
│       ├── PageName.tsx          # 页面容器：只负责布局、数据流、路由参数
│       ├── components/           # 页面私有子组件
│       ├── hooks/                # 页面私有 Hooks
│       ├── types.ts              # 页面私有类型
│       └── utils.ts              # 页面私有工具函数
├── stores/           # Zustand 状态管理
├── theme/            # 主题、色板、Design Token
├── types/            # 项目级类型补充（共享类型优先来自 shared/）
└── utils/            # 纯工具函数
```

**组件封装要求**：

1. **禁止在页面/容器组件内联定义子组件**：`StockDetail.tsx` 中的 `StockFinancial`、`StockResearch`、`StockHeader`、`ErrorState`，以及 `FinancialReport.tsx` 中的 `FinancialReportCard` 必须拆分为独立文件；
2. **单一职责**：一个文件只负责一种 UI 职责（展示、数据准备、交互逻辑）；
3. ** props 优先**：组件间通过 props 通信；跨多级共享状态使用 Context 或 Zustand，避免 props drilling；
4. **Hooks 抽离**：数据获取、副作用、复杂状态管理抽离为 `useXxx` Hook，页面文件保持声明式；
5. **图表组件拆分**：数据转换、ECharts option 构建、交互控件必须拆出，禁止与容器组件耦合。

#### 4.4.2 页面组件拆分

**`web/src/pages/StockDetail/`**

```
pages/StockDetail/
├── StockDetail.tsx           # 仅保留布局与数据流
├── components/
│   ├── StockHeader.tsx
│   ├── StockFinancial.tsx
│   ├── StockResearch.tsx
│   ├── StockChartPanel.tsx
│   ├── StockSectors.tsx      # 已存在，继续保留
│   ├── StockLoadingStatus.tsx # 已存在，继续保留
│   └── ErrorState.tsx
├── hooks/
│   └── useStockDetail.ts
└── types.ts
```

**`web/src/pages/FinancialReport/`**

```
pages/FinancialReport/
├── FinancialReport.tsx
├── components/
│   ├── FinancialReportCard.tsx
│   ├── FinancialReportFilters.tsx
│   └── FinancialReportSummaryModal.tsx
├── hooks/
│   └── useFinancialReports.ts
└── utils.ts                    # summarySnippet / formatFileSize 等页面私有工具
```

**`web/src/pages/Research/`**

```
pages/Research/
├── Research.tsx
├── components/
│   ├── ResearchCard.tsx
│   └── ResearchFilters.tsx     # 如未来过滤条件变复杂可提取
├── hooks/
│   └── useResearchPage.ts      # 将当前页面内查询与分页状态抽离
└── utils.ts                    # summarySnippet
```

**`web/src/pages/Financial/`**

```
pages/Financial/
├── Financial.tsx
├── components/
│   ├── FinancialStatementTable.tsx   # 资产负债表/利润表/现金流量表通用展示
│   └── FinancialDateSelector.tsx     # 报告期选择器
├── hooks/
│   └── useFinancialPage.ts
└── utils.ts                          # buildBalanceRows / buildIncomeRows / buildCashRows / renderPercent
```

**`web/src/pages/Settings/`**

```
pages/Settings/
├── Settings.tsx
├── components/
│   ├── ColorSchemeSelector.tsx
│   ├── MovingAverageConfigList.tsx
│   └── UserProfileCard.tsx
└── utils.ts                    # sortByPeriod / nextDefaultPeriod / nextDefaultColor
```

**`web/src/pages/Hotspot/`**

```
pages/Hotspot/
├── Hotspot.tsx
├── components/
│   └── HotspotFilters.tsx      # 过滤表单（当前直接写在页面中）
├── hooks/
│   └── useHotspotPage.ts
└── utils.ts                    # formatAmount、columns 定义（如较复杂）
```

**`web/src/pages/CapitalFlow/` 与 `web/src/pages/Dashboard/`**

当前已较清晰，可继续保持；若后续增长，按同样模式补充 `components/` 与 `hooks/`。

**`web/src/pages/ChainAnalysis/`**

当前已有 `components/` 子目录且未发现内联子组件，继续保持；建议再提取 `hooks/useChainAnalysis.ts` 将数据流与页面布局进一步解耦。

#### 4.4.3 图表组件拆分

**`web/src/components/charts/StockChartView.tsx` → 拆分为**

```
components/charts/StockChartView/
├── StockChartView.tsx        # 容器：状态、数据加载
├── useKlineData.ts           # 数据准备与转换
├── buildKlineOption.ts       # ECharts option 构建
├── IndicatorButton.tsx       # 指标切换按钮
└── types.ts
```

**`web/src/components/charts/FinancialTrendCharts.tsx` → 拆分为**

```
components/charts/FinancialTrendCharts/
├── FinancialTrendCharts.tsx  # 容器：三大图表布局
├── buildBaseOption.ts        # 通用 ECharts option 基座
├── buildProfitabilityOption.ts
├── buildRevenueOption.ts
├── buildSolvencyOption.ts
└── types.ts
```

**`web/src/components/charts/IndexKlineChart.tsx` / `IntradayChart.tsx`**

当前 option 构建内联在组件内，文件行数可控；建议统一将 option 构建函数提取到同目录 `buildOption.ts`，保持所有图表组件的目录结构一致：

```
components/charts/IndexKlineChart/
├── IndexKlineChart.tsx
└── buildOption.ts
```

**`web/src/components/charts/ChainGraph.tsx`**

- 将 `drawChainBands` 与样式常量移入 `chainGraphUtils.ts`（已部分拆分，继续完善）；
- 节点绘制、状态样式、小地图样式继续收敛到 `chainGraphStyle.ts`。

#### 4.4.4 API 层统一

- 所有映射函数收敛到 `api/mappers/<domain>.ts`：

```
web/src/api/mappers/
├── index.ts
├── market.ts
├── stock.ts
├── chain.ts
├── report.ts
└── user.ts
```

- `api/market.ts` 删除内联 mapper，统一从 `api/mappers/market.ts` 导入；
- 统一使用 `@/api/market` 导入，废弃 `@/api` 再导出模式，或全部走 `@/api/index`。

#### 4.4.5 删除空目录或补充说明

- 删除 `web/src/types/`，或在其中添加 `README.md` 说明共享类型来自 `shared/`。

#### 4.4.6 主题色统一

- 页面中直接使用 `#14161c`、 `#23262e` 等色值的地方，改用 `theme/colors.ts` 中的常量；
- 图表组件统一使用 `theme/colors.ts` 提供的 `panelColors` 与图表专用色板，禁止各自重复定义背景色、网格色、文字色。

#### 4.4.7 Assistant 组件拆分

`components/assistant/` 已按功能域拆分（`composer/`、`messages/`、`ui/`、`hooks/`），但顶层仍有组件职责过重：

**`components/assistant/AssistantPanel.tsx`**

- 内联 `TodoListBar` 子组件 → 提取为 `components/assistant/ui/TodoListBar.tsx`；
- 内联 `clamp`、`readStoredWidth` 工具函数 → 提取到 `components/assistant/utils.ts` 或 `utils/sizing.ts`。

**`components/assistant/AssistantRuntimeProvider.tsx`**

- 内联 `extractTodos`、`extractPageResultFromMessages`、`extractPageResult` 等运行时数据提取函数 → 提取到 `components/assistant/runtimeUtils.ts` 或 `utils/assistantRuntime.ts`；
- 保持 `AssistantRuntimeProvider.tsx` 仅负责组合 runtime 与状态同步。

目标结构示例：

```
components/assistant/
├── composer/
├── hooks/
├── messages/
├── ui/
│   ├── SessionItem.tsx
│   ├── TodoListBar.tsx       # 新增
│   └── ...
├── AssistantPanel.tsx
├── AssistantRuntimeProvider.tsx
├── AssistantSidebar.tsx
├── AssistantThread.tsx
└── utils.ts                  # 存放 assistant 域通用工具函数
```

---

### 4.5 共享层（shared/）重构

#### 4.5.1 拆分 `shared/types/api.ts`

```
shared/types/
├── index.ts
├── user.ts
├── stock.ts
├── market.ts
├── chain.ts
├── report.ts
├── admin.ts
├── collector.ts
└── api/
    ├── index.ts
    ├── request/
    │   ├── user.ts
    │   ├── stock.ts
    │   └── ...
    └── response/
        ├── user.ts
        ├── stock.ts
        └── ...
```

#### 4.5.2 扩展 `shared/utils/`

```
shared/utils/
├── index.ts
├── formatters.ts       # 金额、百分比、涨跌幅格式化
├── industry.ts         # 行业名称规范化
└── validators.ts       # 股票代码校验等
```

#### 4.5.3 自动构建

在 `shared/package.json` 中添加 `prepare` 脚本，并在 `web/package.json` 中声明 `postinstall` 自动构建 shared：

```json
// shared/package.json
{
  "scripts": {
    "build": "tsc",
    "prepare": "npm run build"
  }
}
```

```json
// web/package.json
{
  "scripts": {
    "postinstall": "cd ../shared && npm install && npm run build"
  }
}
```

> 注意：`prepare` 在 `npm install` 时自动执行，但 `file:../shared` 的本地依赖可能需要显式 `postinstall`。

---

### 4.6 Skill / Prompt 统一

#### 方案 A（推荐）：顶层 `skills/` 为唯一真相源

- 保持 `skills/<skill-name>/SKILL.md`；
- 在构建/CI 时通过脚本将 `SKILL.md` 转换为 `backend/app/prompts/skills/<skill-name>.yaml`；
- 删除手写的 `backend/app/prompts/skills/*.yaml`；
- 新增 `limit-up-review`、`market-daily-review` 的 `SKILL.md`。

#### 方案 B：YAML 为真相源

- 删除顶层 `skills/`，所有 Skill 定义移到 `backend/app/prompts/skills/`；
- 在 `docs/` 中生成人类可读的 Skill 目录。

#### 推荐方案 A 的理由

`skills/` 位于项目根目录，更符合开源项目“文档即代码”的理念，也便于非开发者阅读与贡献。

---

### 4.7 测试结构重构

#### 4.7.1 后端测试

```
backend/tests/
├── conftest.py
├── unit/
│   ├── api/
│   ├── services/
│   │   ├── market/
│   │   ├── chain/
│   │   ├── reports/
│   │   └── admin/
│   ├── repositories/
│   ├── agent/
│   ├── collector/
│   │   ├── spiders/
│   │   │   ├── test_sina_spiders.py
│   │   │   ├── test_eastmoney_spiders.py
│   │   │   └── ...
│   │   └── runtime/
│   └── schemas/
└── integration/          # 重新启用
    ├── test_health.py
    ├── test_auth.py
    ├── test_chain_api.py
    └── conftest.py
```

- 将 `test_spiders.py`（1,842 行）按 spider 源拆分为多个文件；
- 将 `test_market_service.py`（1,204 行）按市场域拆分；
- 在 `backend/tests/integration/` 中补充数据库/API 集成测试。

#### 4.7.2 前端测试

```
web/src/
├── __tests__/            # 页面/组件测试
│   ├── pages/
│   └── components/
├── utils/*.test.ts       # 工具函数测试保留并列
└── test/setup.ts
```

- 将现有 co-located 测试逐步迁移到 `__tests__/<domain>/`；
- 扩展 Playwright E2E：至少覆盖产业链分析、股票详情、助手对话三个核心流程。

#### 4.7.3 QA 目录定位

明确 `qa/` 为**端到端/灰度验收测试**，与 `backend/tests/integration/` 区分：

- `backend/tests/integration/`：服务层 + 内存/容器中间件，验证业务逻辑；
- `qa/integration/`：黑盒端到端，验证部署后的关键链路。

---

### 4.8 文档完善

#### 4.8.1 新增标准开源文档

```
.
├── CONTRIBUTING.md              # 贡献指南（开发流程、提交规范、PR 模板）
├── CHANGELOG.md                 # 版本变更日志
├── SECURITY.md                  # 安全策略与漏洞报告方式
├── CODE_OF_CONDUCT.md           # 行为准则（可选）
└── .github/
    ├── ISSUE_TEMPLATE/
    │   ├── bug_report.md
    │   └── feature_request.md
    └── PULL_REQUEST_TEMPLATE.md
```

#### 4.8.2 新增/完善技术文档

- `docs/ops/database-migrations.md`：说明 `docker/database/migrations/` 的执行方式；
- `docs/ops/deployment.md`：整合现有 `docs/arch/06-deployment.md`，补充生产 `.env` 模板；
- `docs/ops/local-development.md`：基于 `Makefile` 和根目录 `docker-compose*.yml` 的本地启动指南；
- `docs/api/README.md`：说明如何查看 `/docs`（OpenAPI）以及生成客户端。

#### 4.8.3 原型文件迁移

`docs/prototypes/` 不是文档，建议迁移到：

```
design/prototypes/   # 根目录下独立设计目录
```

或在 `docs/` 中保留但添加 `README.md` 说明其为历史原型。

---

### 4.9 常量 / 场景定义统一方案

#### 4.9.1 目标

- 消除魔法字符串；
- 前后端共享同一套业务枚举与常量；
- 超时、缓存、颜色、Key 等可配置化；
- 新增业务状态时只需修改一处。

#### 4.9.2 推荐目录结构

```
shared/
├── constants/
│   ├── index.ts
│   ├── status.ts           # success / failed / pending / running / skipped / partial
│   ├── roles.ts            # admin / user / analyst
│   ├── chain.ts            # upstream / midstream / downstream + labels
│   ├── reports.ts          # annual / semi_annual / q1 / q3 + labels
│   ├── collector.ts        # collector task types / statuses
│   ├── skills.ts           # SKILL_ID 注册表
│   ├── colors.ts           # 主题色、图表色板
│   ├── timeouts.ts         # 前后端通用超时（LLM、轮询）
│   └── keys.ts             # Query Key / localStorage Key 前缀与命名规范
└── utils/
    └── ...
```

后端通过 `shared` 包（构建为 Python 可引用的方式）或保持独立 `backend/app/constants/` 镜像：

```
backend/app/constants/
├── __init__.py
├── status.py
├── roles.py
├── chain.py
├── reports.py
├── collector.py
├── skills.py
└── timeouts.py
```

> 推荐方式：以 `shared/constants/` 为唯一真相源，后端在 CI 中通过脚本生成 `backend/app/constants/*.py`，或直接使用 JSON/YAML 配置文件供前后端读取。

#### 4.9.3 状态枚举统一

**后端**：使用 Python `Enum` 或 `Literal`：

```python
from enum import StrEnum

class AnalysisStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    RUNNING = "running"

class UserRole(StrEnum):
    ADMIN = "admin"
    USER = "user"
    ANALYST = "analyst"
```

替换所有 `"success"`、`"failed"`、`"pending"`、`"running"` 魔法字符串为枚举引用。

**前端**：使用 `as const` 对象或 TypeScript 枚举：

```typescript
export const AnalysisStatus = {
  SUCCESS: 'success',
  FAILED: 'failed',
  PENDING: 'pending',
  RUNNING: 'running',
} as const

export type AnalysisStatus = (typeof AnalysisStatus)[keyof typeof AnalysisStatus]
```

#### 4.9.4 业务类型枚举统一

**产业链节点类型**：

```typescript
// shared/constants/chain.ts
export const ChainNodeType = {
  UPSTREAM: 'upstream',
  MIDSTREAM: 'midstream',
  DOWNSTREAM: 'downstream',
} as const

export const CHAIN_NODE_LABELS: Record<ChainNodeType, string> = {
  upstream: '上游 — 原材料与零部件',
  midstream: '中游 — 制造与集成',
  downstream: '下游 — 应用与终端',
}
```

后端对应 Python Enum，前端 `ChainGraph.tsx`、`ChainGraphToolbar.tsx`、`chainGraphStyle.ts` 统一从 `shared/constants/chain.ts` 导入。

**财报类型**：

```typescript
// shared/constants/reports.ts
export const ReportType = {
  ANNUAL: 'annual',
  SEMI_ANNUAL: 'semi_annual',
  Q1: 'q1',
  Q3: 'q3',
} as const

export const REPORT_TYPE_LABELS: Record<ReportType, string> = {
  annual: '年报',
  semi_annual: '半年报',
  q1: '一季报',
  q3: '三季报',
}
```

后端 `financial_report_service.py` 和前端 `FinancialReport.tsx`、`CollectModal.tsx` 统一引用。

#### 4.9.5 超时与缓存策略统一

提取到 `shared/constants/timeouts.ts`：

```typescript
export const TIMEOUTS = {
  LLM_GENERATION: 300_000,
  POLL_INTERVAL: 3_000,
  POLL_TIMEOUT: 90_000,
} as const

export const STALE_TIME = {
  LIVE: 30_000,
  INTRADAY: 5 * 60_000,
  DETAIL: 30 * 60_000,
} as const

export const REFETCH_INTERVAL = {
  LIVE: 60_000,
} as const
```

前端 `hooks/*.ts`、`api/market.ts` 统一引用。后端 LLM 超时继续由 `backend/app/core/config.py` 管理，但配置项命名与 `shared/constants/timeouts.ts` 对齐。

#### 4.9.6 Query Key / Storage Key 统一

统一命名规范：`domain[:subdomain][:identifier]`。

```typescript
// shared/constants/keys.ts
export const QUERY_KEYS = {
  MARKET: ['market'],
  RESEARCH: ['research'],
  FINANCIAL_REPORTS: ['financial-reports'],
  CHAIN_VERSIONS: (industry: string) => ['chain', 'versions', industry],
  CHAIN_LATEST: (industry: string) => ['chain', 'latest', industry],
} as const

export const STORAGE_KEYS = {
  COLOR_SCHEME: 'ai-invest:color-scheme',
  ASSISTANT_SIDEBAR_WIDTH: 'ai-invest:assistant-sidebar-width',
  STOCK_DETAIL_VIEWS: (stockCode: string) => `ai-invest:stock-detail:views:${stockCode}`,
}
```

前端 hook 和组件从 `shared/constants/keys.ts` 导入，禁止各自定义字符串 key。

#### 4.9.7 颜色与图表主题统一

- 所有十六进制色值收敛到 `shared/constants/colors.ts` 或 `web/src/theme/colors.ts`；
- 图表专用色板（ECharts/G6）统一从 `shared/constants/colors.ts` 导出；
- 禁止在业务组件中直接写死 `#14161c`、 `#23262e` 等色值。

```typescript
// shared/constants/colors.ts
export const COLORS = {
  PANEL_BG: '#0c0e12',
  CARD_BG: '#14161c',
  BORDER: '#23262e',
  TEXT_PRIMARY: '#d1d4dc',
  TEXT_SECONDARY: '#8c8c8c',
  UPSTREAM: '#3b82f6',
  MIDSTREAM: '#6366f1',
  DOWNSTREAM: '#10b981',
  BREAKTHROUGH: '#ef4444',
  BOTTLENECK: '#d29922',
} as const
```

#### 4.9.8 SKILL ID 注册表

```typescript
// shared/constants/skills.ts
export const SKILL_ID = {
  INDUSTRY_CHAIN_ANALYSIS: 'industry-chain-analysis',
  MARKET_DAILY_REVIEW: 'market-daily-review',
  LIMIT_UP_REVIEW: 'limit-up-review',
  RESEARCH_REPORT_SUMMARY: 'research-report-summary',
  FINANCIAL_REPORT_SUMMARY: 'financial-report-summary',
} as const
```

后端 `backend/app/services/*.py` 中的 `SKILL_ID = "..."` 统一改为引用 `app.constants.skills.SKILL_ID`。

#### 4.9.9 迁移策略

1. **新增 `shared/constants/`**：先定义所有枚举和常量；
2. **后端镜像**：创建 `backend/app/constants/`，保持与 `shared/constants/` 语义一致；
3. **逐步替换**：按域分批替换魔法字符串，每次替换一个常量类别（如先替换所有状态，再替换所有角色）；
4. **Lint 规则**：配置 ESLint `no-restricted-syntax` 或自定义规则，禁止新增魔法字符串；后端使用 Ruff 检查硬编码状态值。

---

## 5. 实施路线图

### 阶段 1：低风险、高可见（1-2 周）

1. **Docker Compose 整理**
   - 保留 2 个文件在项目根目录：
     - `docker-compose.yml`：本地开发全栈（infra + web + collector + dev volumes）；
     - `docker-compose.prod.yml`：生产部署全栈（infra + web + collector + Caddy）；
   - 废弃 `docker-compose-dev.yml`、`docker-compose.override.yml`、`docker-compose.infra.yml`，将其内容合并到两个全栈文件中；
   - 更新 `Makefile`、`README.md`、服务器 `.env` 中的启动命令，移除 `COMPOSE_FILE` 变量。

2. **文档补齐**
   - 新增 `CONTRIBUTING.md`、`CHANGELOG.md`、`SECURITY.md`；
   - 新增 `.github/ISSUE_TEMPLATE/`、`.github/PULL_REQUEST_TEMPLATE.md`；
   - 新增 `docs/ops/database-migrations.md`。

3. **重复逻辑与常量基础提取**
   - 创建 `shared/utils/industry.ts`、`shared/utils/formatters.ts`；
   - 创建 `shared/constants/` 基础结构：
     - `status.ts`（业务状态枚举）
     - `roles.ts`（用户角色枚举）
     - `colors.ts`（主题色与图表色板）
     - `keys.ts`（Query Key / Storage Key 规范）
   - 创建 `backend/app/constants/` 镜像关键枚举；
   - 替换最明显的魔法字符串：状态值、角色、产业链节点类型、财报类型；
   - 前端替换硬编码色值为 `theme/colors.ts` / `shared/constants/colors.ts`。

### 阶段 2：模块拆分（2-3 周）

1. **后端分层拆分**
   - 同步按业务子域拆分 `services/` 与 `repositories/`，保持 `api/ → services/ → repositories/ → models/` 四层结构；
   - 创建 `services/admin/`、`services/market/`、`services/reports/`、`services/review/`；
   - 创建对应的 `repositories/admin/`、`repositories/market/`、`repositories/reports/`、`repositories/review/`；
   - 拆分 `market_review_service.py`、`stock_service.py`、`financial_report_service.py`；
   - 拆分 `api/v1/assistant.py` 为子包。

2. **前端组件封装与页面拆分**
   - 拆分 `StockDetail.tsx`、`FinancialReport.tsx`、`Research.tsx`、`Financial.tsx`、`Settings.tsx`、`Hotspot.tsx`；
   - 将 `StockFinancial`、`StockResearch`、`StockHeader`、`ErrorState`、`FinancialReportCard`、`ResearchCard` 等内联子组件提取为独立文件；
   - 将页面内内联工具函数（如 `summarySnippet`、`formatFileSize`、`buildBalanceRows`、`sortByPeriod`、`formatAmount`）移入对应 `pages/<Page>/utils.ts`；
   - 拆分 `StockChartView.tsx`、`FinancialTrendCharts.tsx`，统一图表组件目录结构；
   - 拆分 `AssistantPanel.tsx`、`AssistantRuntimeProvider.tsx` 中的内联子组件与工具函数；
   - 每个页面建立 `components/`、`hooks/`（必要时 `utils.ts`）子目录，禁止在页面文件中内联定义子组件；
   - 拆分 `api/mappers.ts` 为 `api/mappers/*.ts`；
   - 在拆分过程中将页面内剩余魔法字符串、色值、超时替换为 `shared/constants/` 引用。

3. **Agent 工具拆分**
   - 按域拆分 `assistant_tools.py`；
   - 统一 session 注入方式；
   - 工具内部状态值与 SKILL ID 改为引用 `app.constants`。

### 阶段 3：深层重构（3-4 周）

1. **常量 / 场景定义全面收敛**
   - 完成 `shared/constants/` 所有类别：timeouts、skills、collector、reports；
   - 后端 `backend/app/constants/` 与 `shared/constants/` 语义对齐；
   - 全量替换剩余魔法字符串，配置 ESLint / Ruff 规则禁止新增；
   - Query Key、Storage Key 全部收敛到 `shared/constants/keys.ts`。

2. **Skill / Prompt 统一**
   - 选择方案 A；
   - 编写 `scripts/build-skills.py` 将 `SKILL.md` 转 YAML；
   - 补充缺失的 Skill Markdown。

2. **共享类型拆分**
   - 拆分 `shared/types/api.ts`；
   - 配置 `shared` 自动构建。

3. **测试结构完善**
   - 拆分 `test_spiders.py`、`test_market_service.py`；
   - 补充 `backend/tests/integration/`；
   - 扩展 `web/e2e/`。

### 阶段 4：验收与固化（1 周）

1. 全量 `uv run ruff check .`、`uv run mypy app/`、`npm run typecheck`、`npm run lint` 通过；
2. 全量单元测试通过；
3. 更新 `docs/arch/` 中受影响的章节；
4. 更新 `CLAUDE.md` 中的目录结构说明。

---

## 6. 验收标准

| 维度 | 目标 | 检查方式 |
|---|---|---|
| 组件封装 | 页面/容器组件不内联定义子组件；单一文件 ≤ 350 行；图表组件数据转换、option 构建、UI 分离 | 搜索 `function .*\({` 内联定义；检查 `pages/*/components/` 目录；审查 `StockDetail.tsx`、`FinancialReport.tsx`、`Research.tsx`、`Financial.tsx`、`Settings.tsx`、`StockChartView.tsx`、`FinancialTrendCharts.tsx`、`AssistantPanel.tsx` |
| 目录清晰度 | 路由层、服务层、数据访问层按业务子域平行分组；禁止 Repository 混入 `services/` | 目录结构 Review；检查 `services/` 内无 `*_repository.py` |
| Docker Compose | 根目录仅保留 2 个 Compose 文件：`docker-compose.yml`（本地开发全栈）与 `docker-compose.prod.yml`（生产部署全栈）；无重复服务定义；`docker-compose-dev.yml` / `docker-compose.override.yml` / `docker-compose.infra.yml` 已废弃 | `ls docker-compose*.yml`；检查本地 `docker compose up -d` 与生产 `docker compose -f docker-compose.prod.yml up -d --build` 可正常启动 |
| 重复代码 | 行业规范化、金额格式化只保留一份 | 代码搜索 `_normalize_industry`、`_format_amount` |
| **常量管理** | **业务状态、角色、类型等无魔法字符串；前后端常量语义一致** | **搜索 `"success"` / `"admin"` / `"upstream"` 等是否仍散落；检查 `shared/constants/` 与 `backend/app/constants/` 覆盖率** |
| 文档 | 具备 `CONTRIBUTING.md`、`CHANGELOG.md`、`SECURITY.md` | 文件存在性检查 |
| 测试 | `backend/tests/integration/` 非空；`test_spiders.py` ≤ 400 行 | 目录/文件检查 |
| 类型安全 | 全量 typecheck / mypy 通过 | CI 检查 |
| 向后兼容 | 所有现有 API URL、请求/响应字段不变 | 回归测试 |

---

## 7. 风险与回退

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| 服务拆分导致循环导入 | 高 | 使用 `__init__.py` facade 模式，子模块不互相导入 |
| 前端组件拆分引入 props drilling | 中 | 拆分同时引入 Context 或继续用 Zustand |
| Skill/Prompt 统一过程中运行时 Prompt 丢失 | 高 | 迁移前备份 `backend/app/prompts/skills/`，新构建脚本验证输出 |
| Compose 文件合并/重命名导致 CI/CD 或本地脚本失效 | 中 | 同步更新 `Makefile`、`.github/workflows/ci.yml`、服务器 `.env`，移除 `COMPOSE_FILE` 变量；保留旧文件作为软链接过渡 1 个版本（可选） |
| shared 自动构建影响本地开发 | 中 | 提供 `make setup` 一键脚本，CI 中显式 `npm run build:shared` |
| 常量替换遗漏导致运行时拼写错误 | 中 | 分域逐步替换，每次替换后跑对应模块单测；Python 使用 `StrEnum` 强制类型检查 |
| 前后端常量不同步 | 中 | `shared/constants/` 为唯一真相源，后端通过生成脚本或共享配置保持同步 |

---

## 8. 附录：关键文件待拆分明细

### 8.1 后端

| 文件 | 当前行数 | 建议拆分方式 |
|---|---|---|
| `backend/app/services/market_review_service.py` | 463 | `services/review/market_review_service.py`（facade）+ `services/review/market_review_generator.py` + `services/review/market_review_formatter.py`；数据访问下沉到 `repositories/review/market_review_repository.py` |
| `backend/app/services/stock_service.py` | 373 | `market/stock_quote_service.py` + `market/stock_kline_service.py` + `market/stock_intraday_service.py` + `market/stock_auction_service.py` + facade |
| `backend/app/api/v1/assistant.py` | 369 | `assistant/threads.py` + `assistant/runs.py` + `assistant/skills.py` + `assistant/page_context.py` |
| `backend/app/agent/runtime/assistant_tools.py` | 389 | `tools/market_tools.py` + `tools/stock_tools.py` + `tools/news_tools.py` + `tools/report_tools.py` + `tools/chain_tools.py` |
| `backend/app/services/chain_service.py` | 351 | 保持，但提取 `chain_analysis_service.py` 负责 analyze/persist |
| `backend/app/services/financial_report_service.py` | 318 | `reports/financial_report_service.py` + `reports/financial_report_summarizer.py` |

### 8.2 前端

| 文件 | 当前行数 | 建议拆分方式 |
|---|---|---|
| `web/src/pages/StockDetail/StockDetail.tsx` | 653 | `components/StockHeader.tsx` + `components/StockFinancial.tsx` + `components/StockResearch.tsx` + `components/StockChartPanel.tsx` + `components/ErrorState.tsx`；将页面私有工具/常量移入 `utils.ts` |
| `web/src/api/mappers.ts` | 611 | `mappers/market.ts` + `mappers/stock.ts` + `mappers/chain.ts` + `mappers/report.ts` |
| `web/src/components/charts/StockChartView.tsx` | 597 | `useKlineData.ts` + `buildKlineOption.ts` + `IndicatorButton.tsx` |
| `web/src/components/charts/ChainGraph.tsx` | 496 | 继续拆分 `chainGraphUtils.ts` |
| `web/src/pages/ChainAnalysis/ChainAnalysis.tsx` | 409 | 已较清晰，可再提取 `hooks/useChainAnalysis.ts` |
| `web/src/pages/Research/Research.tsx` | 283 | `components/ResearchCard.tsx`；将 `summarySnippet` 移入 `utils.ts`；提取 `hooks/useResearchPage.ts` |
| `web/src/components/charts/FinancialTrendCharts.tsx` | 247 | `buildBaseOption.ts` + `buildProfitabilityOption.ts` + `buildRevenueOption.ts` + `buildSolvencyOption.ts` |
| `web/src/components/assistant/AssistantPanel.tsx` | 255 | `ui/TodoListBar.tsx`；将 `clamp` / `readStoredWidth` 移入 `utils.ts` |
| `web/src/pages/Settings/Settings.tsx` | 236 | `components/MovingAverageConfigList.tsx` 等；将 `sortByPeriod` / `nextDefaultPeriod` / `nextDefaultColor` 移入 `utils.ts` |
| `web/src/pages/Financial/Financial.tsx` | 169 | `components/FinancialStatementTable.tsx`；将 `buildBalanceRows` / `buildIncomeRows` / `buildCashRows` / `renderPercent` 移入 `utils.ts` |
| `web/src/components/assistant/AssistantRuntimeProvider.tsx` | 148 | 将 `extractTodos` / `extractPageResultFromMessages` / `extractPageResult` 移入 `utils/assistantRuntime.ts` |
| `web/src/pages/FinancialReport/FinancialReport.tsx` | 317 | `components/FinancialReportCard.tsx` + `components/FinancialReportFilters.tsx` + `components/FinancialReportSummaryModal.tsx`；将 `summarySnippet` / `formatFileSize` 移入 `utils.ts` |

### 8.3 测试

| 文件 | 当前行数 | 建议拆分方式 |
|---|---|---|
| `backend/tests/unit/collector/test_spiders.py` | 1,842 | 按数据源拆分为 `test_sina_spiders.py`、`test_eastmoney_spiders.py`、`test_cninfo_spiders.py` 等 |
| `backend/tests/unit/services/test_market_service.py` | 1,204 | 按市场子域拆分为 `test_quote_service.py`、`test_kline_service.py`、`test_auction_service.py` 等 |

---

*本方案由 Claude Code 根据当前代码库 Review 生成，建议与核心维护者确认优先级后分阶段实施。*
