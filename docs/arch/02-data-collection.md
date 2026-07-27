# 数据采集引擎架构

## 1. 采集引擎总览

采集模块独立于 Web API，位于 `backend/collector/`，是**声明式 + 多渠道 fallback**的 runtime：
所有任务在 `runtime/registry.py` 的 `TASK_SPECS` 注册表声明，新增数据源只需扩展声明表与 spider 类，
无需改动 runner / scheduler / API。

```
┌────────────────────────────────────────────────────────────────────────────┐
│                          采集 runtime 总览                                   │
│                                                                            │
│  触发方式（共用同一份 runtime）                                              │
│  ├── SCF Job（Timer） → runtime.scf_handler → runtime.cli → runner.run_task │
│  ├── 常驻 worker       → runtime.worker ← Redis 队列 → runner.run_task       │
│  ├── 调度器            → runtime.scheduler（cron）→ Redis 队列              │
│  └── 管理后台 API      → runtime.dispatcher（投递）→ Redis 队列              │
│                                                                            │
│  runtime/                                                                  │
│  ├── registry.py     TaskSpec 声明表（任务参数 + 渠道懒加载路径）             │
│  ├── resolver.py     按 collector_channel_data_type 优先级解析可用渠道       │
│  ├── channels.py     渠道配置数据访问                                        │
│  ├── queue.py        Redis 队列封装                                         │
│  ├── dispatcher.py   后台 API → 队列                                        │
│  ├── scheduler.py    cron → 队列                                            │
│  ├── worker.py       常驻消费循环                                            │
│  ├── runner.py       统一执行器（collector_log 唯一写入点）                  │
│  ├── cli.py          CLI 入口（SCF Job / 本地脚本）                          │
│  └── scf_handler.py  SCF 事件解析                                            │
│                                                                            │
│  core/    base(PostgresCollector/共享 engine) / http_client / parsing /     │
│           pipelines / exporters / locks / calendar / logging / config       │
│  spiders/ 各数据源采集器（声明表配置 + collect/transform）                   │
│  stores/  重存储编排（financial_report_store / research_report_store）       │
└────────────────────────────────────────────────────────────────────────────┘
```

## 2. 调度与执行入口

### 2.1 三种触发方式共享同一执行器

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ SCF Timer     │  │ scheduler    │  │ dispatcher   │  │ CLI/本地脚本 │
│ (云函数触发)  │  │ (常驻 cron)  │  │ (后台 API)   │  │              │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │ scf_handler      │ 入队            │ 入队            │
       ▼                  ▼                 ▼                 ▼
   runtime.cli     ──────► Redis 队列 ◄──────              runtime.cli
                            (collector:queue)
                                  │
                                  ▼
                        ┌──────────────────┐
                        │ runtime.worker   │ ← 常驻消费循环（也可由 cli 单跑）
                        └────────┬─────────┘
                                 │
                                 ▼
                        ┌──────────────────┐
                        │ runtime.runner   │ 生成 task_run_id，回写 collector_log
                        │   .run_task      │ 失败记录 traceback
                        └────────┬─────────┘
                                 │
                                 ▼
                        ┌──────────────────┐
                        │ registry 解析    │ 按 TaskSpec 拉起对应 spider
                        │ 多渠道 fallback  │ 失败自动切换下一渠道
                        └──────────────────┘
```

`docker/collector/entrypoint-collector.sh` 通过环境变量 `COLLECT_TASK` 选择执行模式：
- 设置 `COLLECT_TASK=<task>` → 跑一次性任务后退出（适配 SCF Job）
- 未设置 → 启动常驻 worker（监听 Redis 队列）

### 2.2 调度矩阵（参考）

```
┌──────────────────┬──────────────────┬──────────────────────────────────┐
│ 任务              │ 触发节奏          │ 备注                              │
├──────────────────┼──────────────────┼──────────────────────────────────┤
│ kline            │ 交易日 16:00 起   │ sina → ths fallback               │
│ index-kline      │ 交易日盘后        │ 仅 sina                           │
│ etf-kline        │ 交易日盘后        │ 沪深 300 ETF                      │
│ a50-kline        │ 交易日盘后        │ 富时 A50（东财）                  │
│ stock-minute     │ 交易日盘后        │ 个股分钟线                        │
│ index-minute     │ 交易日盘后        │ 指数分钟线                        │
│ index-auction    │ 交易日盘前 9:15   │ Tushare stk_auction 聚合          │
│ sector-fund-flow │ 交易日盘后        │ 东财（行业）/ 同花顺（概念）      │
│ fund-flow        │ 交易日盘后        │ 东财个股资金流                    │
│ limit-up-pool    │ 交易日盘后        │ 东财官方涨停池                    │
│ limit-down-pool  │ 交易日盘后        │ 东财跌停池                       │
│ dragon-list      │ 交易日盘后        │ 东财龙虎榜                       │
│ broken-pool      │ 交易日盘后        │ 东耳炸板池                       │
│ market-breadth   │ 交易日盘后        │ sina 市场宽度                    │
│ market-amount    │ 交易日盘后        │ 上交所/深交所成交流水             │
│ index-spot       │ 盘中实时          │ sina 指数 spot                    │
│ quote            │ 盘中实时          │ sina 个股实时行情                 │
│ stock-list       │ 每日              │ sina 全市场列表 + 字段补全        │
│ company-profile  │ 每日              │ 巨潮资讯公司信息                  │
│ disclosure       │ 每小时            │ 巨潮资讯公告                      │
│ financial-report │ 每日 / 财报季密集 │ 东财结构化 / 巨潮 PDF（双源）     │
│ research-report  │ 每日 9,18         │ 东财研报                          │
│ fund-holdings    │ 每季              │ 东财基金持仓                      │
│ ipo-info         │ 每日              │ 巨潮 IPO 信息                     │
│ concept-constit. │ 每日              │ 东财概念成分股                    │
│ news             │ 每 30 分钟        │ sina 财经新闻                    │
│ macro            │ 按需              │ sina 宏观指标                    │
│ market-daily-... │ 交易日盘后        │ internal 渠道，汇总当日复盘数据  │
└──────────────────┴──────────────────┴──────────────────────────────────┘
```

> 具体时间在 `runtime/scheduler.py` 与 `docker/database/init-scripts/03-seed.sql` 的种子任务表中维护。

## 3. 注册表驱动的任务声明

### 3.1 TaskSpec 结构

每个任务在 `runtime/registry.py` 声明一条 `TaskSpec`：

```python
@dataclass(frozen=True)
class TaskSpec:
    name: str                            # 任务名（与 collector_task.task_type 对应）
    data_type: str                       # 写入 collector_log/渠道解析的数据类型；支持 {param}
    collectors: dict[str, str]           # source -> "module:Class" 懒加载路径
    config_params: tuple[str, ...] = ()  # 透传到 collector config 的任务参数
    run_params: tuple[str, ...] = ()     # 透传到 collector.run(**kwargs) 的参数
    defaults: dict[str, Any] = field(default_factory=dict)
    converters: dict[str, Callable] = field(default_factory=dict)

    @property
    def param_keys(self) -> tuple[str, ...]:
        return self.config_params + self.run_params
```

新增采集任务的典型声明：

```python
TaskSpec(
    name="concept-constituents",
    data_type="mapping_stock_concept",
    collectors={
        "eastmoney": "collector.spiders.eastmoney_concept_constituents:EastmoneyConceptConstituentCollector",
    },
),
TaskSpec(
    name="sector-fund-flow",
    data_type="capital_fund_flow_sector",
    collectors={
        "eastmoney": "collector.spiders.eastmoney_sector_fund_flow:EastMoneySectorFundFlowCollector",
        "ths": "collector.spiders.ths_sector_fund_flow:ThsSectorFundFlowCollector",
    },
    run_params=("sector_type", "trade_date"),
    converters={"trade_date": date.fromisoformat},
),
```

runner 的任务参数白名单从 `TASK_SPECS` 派生，参数只在声明表维护一处。

### 3.2 多渠道 fallback

`_run_collector_for_task` 按 `resolve_channels_for_task` 返回的优先级顺序逐个尝试：

- 渠道未启用 / 该任务无对应采集器 → 记录 `[source] 渠道没有任务 X 对应的采集器`，跳到下一个
- 采集器返回 `FAILED` / `SKIPPED` → 记录错误，尝试下一渠道
- 任意渠道返回 `SUCCESS` / `PARTIAL` → 立即返回；其余失败渠道的错误合并进 `result.errors`

> 设计要点：多渠道任务的 fallback 依赖异常向上传播，spider 内除已知"无数据即抛错"的接口（涨停池 / 龙虎榜）外，不要 try/except 吞异常返回空列表。

### 3.3 渠道优先级管理

渠道优先级通过管理后台维护，数据由两张表承载：

- `collector_channel_config` — 渠道级配置（source / base_url / api_key / extra JSON）
- `collector_channel_data_type` — 渠道 × 数据类型 优先级关联表

`resolver.resolve_channels_for_task` 根据 `TaskSpec.data_type` 查询启用的渠道并按优先级排序。

## 4. Spider 基类

### 4.1 PostgresCollector（声明式基类）

绝大多数写入 PostgreSQL 的 spider 继承 `core.base.PostgresCollector`，只需声明类属性并实现 `collect`：

```python
class SinaKlineCollector(PostgresCollector):
    table = "quote_kline_stock_daily"   # 目标表
    conflict_key = ["stock_code", "trade_date"]   # ON CONFLICT 列
    update_columns = ["open", "high", "low", "close", "volume", "amount", ...]
    key_fields = ("stock_code", "trade_date")     # 业务键（用于去重）
    required_fields = ("stock_code", "trade_date", "close")  # 必填校验

    async def collect(self, *, period: str = "daily", **kwargs) -> list[dict]:
        # 调用数据源接口，返回原始 dict 列表
        ...
```

- `transform` 默认透传，子类按需覆写做字段映射
- `validate` 默认按 `required_fields` 校验，缺字段记一条 error 后跳过
- 不要自建 engine / pipeline / store — 共享 PostgresCollector.engine 与默认 pipeline

> 新增 DB 类采集器通常不超过 30 行。

### 4.2 配对渠道的共享基类

同一数据类型的多渠道 spider 共用 `spiders/` 下的数据类型基类，子类只写 `collect` 与数据源键名：

| 共享基类 | 子类（渠道） |
|----------|--------------|
| `kline_base.py` | `sina_kline` / `ths_kline` |
| `auction_base.py` | `sina_auction` / `ths_auction` |
| `sector_fund_flow_base.py` | `eastmoney_sector_fund_flow` / `ths_sector_fund_flow` |

新增同类渠道优先复用 / 扩展这些基类，禁止复制粘贴字段映射逻辑。

### 4.3 重存储编排（stores/）

`stores/` 承载需要复杂文件 / 元数据 / 多步写入的采集：

- `financial_report_store.py` — 东财结构化 + 巨潮 PDF 双源；下载 PDF 入 MinIO，元数据写 `file_metadata`，触发 AI 摘要时回写 `summary` 列
- `research_report_store.py` — 东财研报下载；通过 `curl_cffi` 模拟 Chrome TLS 指纹绕过 `pdf.dfcfw.com` 的 WAF

> 同样写入 collector_log，但走自己的事务边界（不经过 `get_db`）。

## 5. 解析与容错约定

- **解析函数只用 `core.parsing`**：`to_optional_str` / `to_float` / `parse_cn_amount` / `clean_stock_code` / `parse_date` / `parse_time` — 禁止在 spider 内重复定义
- **akshare 容错**：空数据（`df is None or df.empty`）返回 `[]`；异常向上传播以便 fallback 生效
- **HTTP 客户端**：东财 push2/push2his 已被 IP 封禁，统一走 `core.http_client` 中的限流客户端；同花顺作为备用源
- **日志**：入口调用 `core.logging.configure_logging()`，禁止 `logging.basicConfig`；任务日志自动携带 `task_run_id` / `task` / `source`
- **配置**：用 `core.config`（委托 `app.core.config`），禁止新增环境变量读取点

## 6. 容错与监控

```
监控策略
  ├── collector_log（PostgreSQL，runner 唯一写入点）
  │     ├── task_run_id / task / source / status / 数据量
  │     ├── started_at / finished_at / errors[] / traceback
  │     └── 每次执行一条记录，便于按任务/渠道/日期审计
  │
  ├── 多渠道 fallback
  │     └── 失败自动切换下一渠道，最终失败时合并所有尝试的错误
  │
  └── 失败重试
        ├── SCF 异步重试（云函数内置）
        └── 下一次 Timer 触发自动覆盖（增量采集天然容错）
```

`runner.run_task` 是 `collector_log` 的**唯一写入点**：
- 生成 `task_run_id` 绑定 structlog 上下文
- 成功 / 部分成功 / 失败 / 跳过 各自写入对应 `status`
- 异常时记录 traceback，避免 collector_log 与 worker/cli/scf_handler 多处写入造成口径分裂

## 7. 后续文档索引

- [01-data-source.md](./01-data-source.md) — 数据源详细分析
- [03-data-storage.md](./03-data-storage.md) — 数据库设计与命名约定
- [04-ai-agent.md](./04-ai-agent.md) — AI Agent 体系（采集 → Skill 数据工具）
- [06-deployment.md](./06-deployment.md) — SCF Job / worker 部署方案
