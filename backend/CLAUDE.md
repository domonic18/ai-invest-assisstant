# AI Invest Assistant Backend - Claude Code AI 上下文文件

> 本目录下的规则是对项目根目录 [CLAUDE.md](../CLAUDE.md) 通用规则的补充。请先阅读根目录的通用规则。

## 1. 技术栈

- **Python**: 3.10+
- **Web 框架**: FastAPI 0.111+ / Uvicorn
- **ORM**: SQLAlchemy 2.0+ / Alembic
- **数据验证**: Pydantic 2.7+ / Pydantic Settings
- **AI Agent**: deepagents (LangChain/LangGraph) / OpenAI SDK / Anthropic SDK
- **MCP**: mcp 1.x
- **配置管理**: Pydantic Settings + YAML 配置文件
- **日志**: structlog
- **测试**: pytest

## 2. Python 编码规范

### 类型提示（必需）

- **始终**为函数参数和返回值使用类型提示
- 对复杂类型使用 `from typing import` 或 `collections.abc`
- 优先使用 `Optional[T]` 而不是 `Union[T, None]`
- 对数据结构使用 Pydantic 模型

```python
# 良好示例
from typing import Optional, Dict, Any
from collections.abc import AsyncIterator

async def get_stock_metrics(
    code: str,
    start_date: datetime,
    end_date: datetime,
    include_cache: bool = True,
) -> Optional[Dict[str, Any]]:
    """获取股票指标数据。"""
    pass
```

### 命名约定

| 类型 | 规范 | 示例 |
|------|------|------|
| 类 | PascalCase | `BaseCollector`, `StockService` |
| 函数/方法 | snake_case | `fetch_kline`, `calculate_metrics` |
| 常量 | UPPER_SNAKE_CASE | `MAX_RETRIES`, `DEFAULT_PAGE_SIZE` |
| 私有方法 | 前导下划线 | `_validate_input` |
| Pydantic 模型 | PascalCase | `StockResponse` |
| 数据库模型 | PascalCase | `Stock`, `KLine` |
| API 端点 | snake_case | `get_stock_detail` |

### 文档要求

- 每个模块需要文档字符串
- 每个公共函数需要文档字符串
- 使用 Google 风格的文档字符串
- 在文档字符串中包含类型信息

```python
async def fetch_kline(
    self,
    params: Optional[Dict[str, Any]] = None,
) -> CollectorResult[List[KLine]]:
    """采集 K 线数据。

    Args:
        params: 采集参数，包含时间范围等筛选条件

    Returns:
        采集结果，包含 K 线数据列表和采集元信息

    Raises:
        CollectorConnectionError: 网络连接失败
        CollectorAuthenticationError: 认证失败
        CollectorRateLimitError: API 限流
    """
    pass
```

## 3. 架构规范

### 薄路由、重服务的分层架构

- 路由层只处理 HTTP 逻辑（参数验证、响应格式、状态码、异常转换）
- 业务逻辑在服务层实现
- 正确使用 HTTP 状态码
- 使用一致的 JSON 响应格式
- 列表端点支持分页

### 数据库分层与事务边界（必须遵守）

分层：`路由 (api/) → 服务 (services/) → 仓储 (repositories/) → 模型 (models/)`

- **services 与 repositories 按业务子域组织**：`services/` 与 `repositories/` 根目录不存放平文件，
  新服务/仓储一律放入对应子域包（admin/ assistant/ chain/ collector/ common/ market/ reports/ review/ user/）；
  services 顶层禁止导入 `app.agent.tools` / `app.agent.skills` / `app.agent.runtime`
  （它们反向依赖 services，顶层导入会成环，需在函数内延迟导入）；
  `app.agent.core`（Prompt 加载/渲染等纯配置叶子）可顶层导入
- **路由层禁止直接操作数据库**：不允许在路由中调用 `session.execute` / `session.add` / `session.commit`，一律委托给服务层
- **仓储层禁止管理事务**：`repositories/` 只做查询构造与执行，**绝不**调用 `commit()` / `rollback()`
- **服务层拥有事务边界**：所有写操作（add/delete/update）成功后必须显式 `await session.commit()`；禁止只 `flush()` 不 `commit()`（`get_db` 不会自动提交，只 flush 的写入会在请求结束时被回滚）
- **独立执行单元自行管理事务**：`collector/` 下的 worker、dispatcher、store 等不经过 `get_db` 的代码，必须在自己创建的 session 上显式 commit
- **批量写入容错**：循环写入单条失败时，使用 `session.begin_nested()`（SAVEPOINT）隔离失败项，避免污染整个会话
- **`get_db` 的唯一实现位于 `app/dependencies/__init__.py`**，异常时自动回滚；不要在其他模块重复定义

### 数据库命名规范

新增或重命名表/字段时遵循以下约定（完整重构计划见 `docs/plan/database-refactoring-plan.md`）：

- **表名**：小写蛇形、单数名词，同一业务分类使用统一前缀。
  - 行情数据：`quote_`（如 `quote_kline_stock_daily`、`quote_auction_index`）
  - 资金流向：`capital_`（如 `capital_fund_flow_stock`、`capital_fund_flow_sector`）
  - 市场情绪：`market_`（如 `market_breadth`）
  - 股池：`pool_`（如 `pool_limit_up_stock`）
  - 财务报表：`financial_`（如 `financial_balance_sheet`）
  - 产业链：`industry_chain_`（如 `industry_chain_company_mapping`）
  - 成分/映射：`mapping_`（如 `mapping_index_stock`）
- **表名结构**：`<分类前缀>_<数据类型>_<标的类型>[_<粒度/子类型>]`，无标的类型的市场级数据可省略 `<标的类型>`。
- **字段名**：完整单词优先，禁用无上下文缩写；同一语义使用同一单词（如涨跌幅统一用 `change_pct`）。
- **约束与索引命名**：`pk_<table>`、`uq_<table>_<columns>`、`fk_<table>_<ref_table>`、`idx_<table>_<columns>`、`chk_<table>_<column>`。
- **审计字段**：业务表统一使用 `created_at`/`updated_at`。

### 时间与时区规范（必须遵守）

A 股业务日期与时区不一致曾导致复盘/调度类事故，以下约定为强制项：

- **业务"今天"统一用 `app.core.clock`**：`today_cn()`（Asia/Shanghai 日历日）、
  `CN_TZ`/`now_cn()`。禁止用 `date.today()`（依赖容器本地时区）或
  `datetime.now(timezone.utc).date()`（00:00-08:00 CST 会落在前一日）作为交易日、
  日期区间默认值等业务日期。
- **时间戳统一用 aware UTC**：数据库 `timestamptz` 字段与日志时间用
  `datetime.now(timezone.utc)`；禁止 naive 的 `datetime.utcnow()`。
- **Celery 调度一律按 Asia/Shanghai 意义书写**：`celery_app.conf` 已显式设置
  `timezone="Asia/Shanghai"`，cron 表达式（`collector_task.schedule` 及
  `docker/database/init-scripts/03-seed.sql`）中的小时均为北京时间；
  应用容器（web/beat/worker）必须注入 `TZ: Asia/Shanghai` 环境变量。
- **前端渲染时间戳不得写死时区字面量**：用 dayjs 按 ISO 时间（UTC）解析后本地化
  格式化；测试断言期望值须由同一 fixture 推导，禁止硬编码本地时间字符串。

### Collector 分层结构

```
collector/
├── core/       # 基础设施：base(BaseCollector/PostgresCollector/共享 engine)、
│               #   pipelines、exporters、http_client、parsing、logging、config
├── runtime/    # 执行层：runner(统一执行器/collector_log 唯一写入口)、
│               #   registry(TaskSpec 声明表 + 多渠道 fallback)、resolver、channels、
│               #   queue、dispatcher、scheduler、worker、cli、scf_handler
├── spiders/    # 数据源采集器（声明表配置 + collect/transform）
└── stores/     # 重存储编排（如 financial_report_store）
```

- **新增 DB 类采集器**：继承 `core.base.PostgresCollector`，声明 `table`/`conflict_key`/`update_columns`/`key_fields`/`required_fields` 类属性并实现 `collect`（`transform` 默认透传、`validate` 默认按 required_fields 校验，可按需覆写），通常不超过 30 行；不要自建 engine/pipeline/store
- **同一数据类型的多渠道 spider**（如 sina/ths 的 kline、auction、eastmoney/ths 的 sector-fund-flow）：共用 `spiders/` 下的数据类型基类（`kline_base.py`/`auction_base.py`/`sector_fund_flow_base.py`），子类只写 collect 与数据源键名声明；新增同类渠道优先复用/扩展这些基类
- **解析函数只用 `core.parsing`**（`to_optional_str`/`to_float`/`parse_cn_amount`/`clean_stock_code`/`parse_date`/`parse_time`），禁止在 spider 里重复定义
- **akshare 容错约定**：空数据（`df is None or df.empty`）返回 `[]`；异常不要吞——多渠道任务的 fallback 依赖异常向上传播，仅已知"无数据即抛错"的接口（如涨停池/龙虎榜）可 try/except 返回 `[]`
- **新增采集任务**：在 `runtime/registry.py` 的 TASK_SPECS 增加一条 TaskSpec 声明（data_type/采集器懒加载路径/config_params/run_params），任务参数只在此维护一处，runner 的参数白名单自动派生
- **任务目录 API 从 TASK_SPECS 派生**（`GET /admin/collector/tasks/catalog`）：API/UI 一律从目录取任务清单，禁止在枚举、shared 类型或前端另行硬编码；SKIPPED 是采集器的良性终态（非交易日/已生成），fallback 只对 FAILED 轮换渠道，不得把 SKIPPED 改写为 FAILED
- **日期类参数默认值必须是 `latest_trading_day()`**（股池/龙虎榜/成交额/复盘均如此），禁止 `today_cn()`/`now` 兜底——周末手动补跑会静默空采；仅"天然只有当日"的数据（auction 快照、新浪分钟线）可用当日
- **执行入口统一走 `runtime.runner.run_task`**（worker/scheduler/CLI/SCF 共享）：生成 `task_run_id` 绑定日志上下文、回写 `collector_log`、失败记录 traceback；`runtime/scf_handler.py` 只做 SCF 事件解析
- **日志**：入口调用 `core.logging.configure_logging()`，禁止 `logging.basicConfig`；任务日志自动携带 `task_run_id`/`task`/`source`
- **配置**：用 `core.config`（委托 `app.core.config`），禁止新增环境变量读取点

### AI Agent 与 Prompt 管理

- 所有 Agent Prompt 必须放在 `app/prompts/agents/` 和 `app/prompts/skills/` 下的 YAML 文件中
- 禁止在 Python 代码中硬编码 Prompt
- 使用 `PromptLoader` 加载配置、`PromptRenderer` 渲染模板
- 使用 `model_factory.build_langchain_model()` 统一创建模型；多步任务走 `agent/skills/skill_runtime` deepagents 骨架，单轮结构化任务走 `agent/runtime/structured.run_structured`

### 可观测系统与日志标准

- 使用 structlog 进行结构化日志记录
- 日志按模块分离：app logs, collector logs
- 为机器而不是人类构建日志 - 使用 JSON 格式，带一致字段（时间戳、级别、事件、上下文）

### 状态管理

- 每个状态片段有一个真相来源
- 让状态变更明确且可追踪
- 缓存失效策略要明确

## 4. 开发工具链

**统一使用 `uv`（不是 pip/python3）**：

```bash
# 运行 FastAPI 服务
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 运行测试
uv run pytest
uv run pytest -m unit
uv run pytest -xvs tests/unit/test_example.py

# 类型检查
uv run mypy app/

# 代码 lint
uv run ruff check .
uv run ruff check --fix .

# 同步依赖
uv sync

# 添加依赖
uv add <package>

# 添加开发依赖
uv add --group dev <package>
```

## 5. 测试规范

测试标记：

- `unit`: 单元测试，无外部依赖，快速执行
- `integration`: 集成测试，需要数据库/Redis/ES 等中间件
- `database`: 数据库测试
- `collector`: 采集器测试
- `api`: API 接口测试
- `mcp`: MCP 接口测试

## 6. 任务完成后检查清单

完成后端编码任务后：

1. **类型安全**：`uv run mypy app/`
2. **测试**：`uv run pytest -m unit`
3. **代码质量**：`uv run ruff check .`
4. **验证**：API 端点的输入验证和错误处理
5. **文档**：确保代码注释和文档字符串保持最新
