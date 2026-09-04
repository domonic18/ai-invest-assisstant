# 数据采集引擎架构

## 1. 采集引擎总览

采集模块独立于 Web API，位于 `backend/collector/`，是**声明式注册表 + 多渠道 fallback**的 runtime，
执行载体为 **Celery**（beat 调度 + 3 个队列 worker）。所有任务在 `runtime/registry.py` 的
`TASK_SPECS` 注册表声明，新增数据源只需扩展声明表与 spider 类，无需改动 runner / 调度 / API。

```
┌────────────────────────────────────────────────────────────────────────────┐
│                          采集 runtime 总览                                   │
│                                                                            │
│  collector/ 顶层（Celery 装配）                                             │
│  ├── celery_app.py    Celery 应用（timezone=Asia/Shanghai，3 队列）         │
│  │                    collector.realtime / collector.batch / collector.heavy│
│  ├── celery_beat.py   CollectorDatabaseScheduler：collector_task 表为       │
│  │                    调度唯一真相源，beat 周期同步 DB（改行即生效）         │
│  └── celery_tasks.py  任务投递封装 + NotReady 自动重试（见 §6）              │
│                                                                            │
│  runtime/                                                                   │
│  ├── registry.py     TaskSpec 声明表（33 任务：参数 + 渠道懒加载路径）       │
│  ├── resolver.py     按 collector_channel_data_type 优先级解析可用渠道       │
│  ├── channels.py     渠道配置数据访问                                        │
│  ├── dispatcher.py   管理后台 API → Celery 队列投递                         │
│  ├── runner.py       统一执行器 run_task（collector_log 唯一写入点）         │
│  ├── cli.py          CLI 入口（本地调试 / 应急）                             │
│  └── scf_handler.py  SCF 事件解析（云函数承载时的适配层）                    │
│                                                                            │
│  core/    base(PostgresCollector/共享 engine) / http_client / parsing /     │
│           pipelines / exporters / calendar / logging / config               │
│  spiders/ 各数据源采集器（声明表配置 + collect/transform）                   │
│  stores/  重存储编排（financial_report_store / research_report_store）       │
└────────────────────────────────────────────────────────────────────────────┘
```

## 2. 调度与执行入口

### 2.1 四种触发方式共享同一执行器

```
┌────────────────────┐ ┌────────────────┐ ┌──────────────┐ ┌─────────────┐
│ celery-beat         │ │ 管理后台 API    │ │ CLI/本地脚本 │ │ SCF 事件     │
│ collector_task 表   │ │ dispatcher 投递│ │ runtime.cli  │ │ scf_handler │
└─────────┬──────────┘ └───────┬────────┘ └──────┬───────┘ └──────┬──────┘
          │ 按 schedule 投递    │                 │ 直接调用        │
          ▼                    ▼                 ▼                ▼
   ┌────────────────────────────────┐                          runtime.cli
   │ Celery 队列                     │
   │ realtime(实时) / batch(批量) /  │
   │ heavy(LLM 长任务, 并发=1)       │
   └──────────────┬─────────────────┘
                  ▼
   ┌────────────────────────────────┐
   │ runtime.runner.run_task        │ 生成 task_run_id，回写 collector_log，
   │ （worker/scheduler/CLI/SCF 共享）│ 失败记录 traceback
   └──────────────┬─────────────────┘
                  ▼
   ┌────────────────────────────────┐
   │ registry 解析 → 拉起 spider     │ 多渠道 fallback（仅 FAILED 轮换）
   └────────────────────────────────┘
```

`docker/collector/entrypoint-collector.sh` 通过环境变量选择进程角色：

- `COLLECTOR_MODE=beat` → celery-beat（挂 `CollectorDatabaseScheduler`）
- `COLLECTOR_MODE=worker` + `COLLECTOR_QUEUE=<queue>` → 队列 worker
- `COLLECTOR_MODE=stream` → 准实时驻留采集进程（财联社电报 10 秒增量轮询，自有循环、不走 Celery 队列，不注册 TASK_SPECS）
- 设置 `COLLECT_TASK=<task>` → 跑一次性任务后退出（CLI / SCF 模式）

### 2.2 调度矩阵（节奏参考）

调度真相源是 `collector_task` 表（种子见 `docker/database/init-scripts/03-seed.sql`），
beat 周期同步，在管理后台改行即生效；下表仅列节奏概况，**具体 cron 以表内容为准**：

| 任务 | 渠道 | 节奏 |
|------|------|------|
| kline_{daily,weekly,monthly} | sina（唯一） | 交易日盘后 |
| index-kline / etf-kline / a50-kline | sina / 东财 | 交易日盘后 |
| stock-minute / index-minute | sina | 交易日盘后 |
| index-auction（指数集合竞价） | tushare（唯一） | 交易日 9:15 盘前 |
| auction（个股集合竞价） | sina → ths | 交易日盘前 |
| market-amount（市场成交额） | exchange（唯一） | 交易日盘中/盘后 |
| sector-fund-flow（板块资金流） | eastmoney → ths | 交易日盘后 |
| fund-flow（个股资金流） | eastmoney | 交易日盘后 |
| limit-up-pool / limit-down-pool / broken-pool | eastmoney | 交易日 16:00 盘后 |
| dragon-list（龙虎榜） | eastmoney | 交易日盘后 |
| market-breadth / index-spot / quote / stock-list | sina | 盘中高频 / 每日 |
| concept-constituents（概念成分股） | eastmoney（curl_cffi） | 每日 |
| news / macro | sina | 每 30 分钟 / 按需 |
| cls-telegraph（财联社电报快讯） | cls | 驻留进程 10 秒增量轮询（非 beat 调度，见 §2.1 stream 角色），lastTime 游标断点续传 |
| company-profile / disclosure / financial-report / ipo-info | cninfo | 每日 / 公告小时级 / 财报季密集 |
| research-report / fund-holdings | eastmoney | 每日两次 / 每季 |
| market-daily-review（每日复盘） | internal | 交易日 15:05，LLM 生成 |
| limit-up-ai-review（涨停AI归因） | internal | 交易日 16:30（依赖 16:00 涨停池），LLM 生成 |
| watchlist-daily-analysis（自选股AI分析） | internal | 交易日盘后（heavy），仅遍历开启 AI 复盘开关的分组，LLM 生成 |
| invest-calendar（投资日历） | cls（调研项） | 每日增量；Fed/BLS 固定日程每年初导入 |
| global-index（全球指标） | eastmoney → tushare | 交易日盘中低频 + 盘后收盘价落库 |

> internal AI 任务结果按 `input_hash`（skill_id + 业务键：复盘/归因为日期，自选股分析为 code+日期）缓存于 `ai_analysis_result`，已生成则 SKIPPED（良性终态）。

## 3. 注册表驱动的任务声明

### 3.1 TaskSpec 结构

每个任务在 `runtime/registry.py` 声明一条 `TaskSpec`：

```python
@dataclass(frozen=True)
class TaskSpec:
    name: str                            # 任务名（与 collector_task.task_type 对应）
    label: str                           # 中文展示名（目录 API / 前端标签）
    data_type: str                       # 渠道解析键；支持 {param} 模板（如 kline_{period}）
    collectors: dict[str, str]           # source -> "module:Class" 懒加载路径
    queue: str = ...                     # Celery 队列（_QUEUE_OVERRIDES 集中覆盖，如 heavy）
    soft_time_limit: int = ...           # 软超时（LLM 任务放宽）
    max_retries: int = ...               # Celery 重试次数
    config_params: tuple[str, ...] = ()  # 透传到 collector config 的任务参数
    run_params: tuple[str, ...] = ()     # 透传到 collector.run(**kwargs) 的参数
    defaults: dict[str, Any] = ...       # 参数默认值（日期类一律 latest_trading_day()）
    converters: dict[str, Callable] = ...  # 参数类型转换（如 date.fromisoformat）
```

新增采集任务的典型声明：

```python
TaskSpec(
    name="limit-up-ai-review",
    label="涨停AI归因",
    data_type="ai_limit_up_review",
    collectors={"internal": "collector.spiders.limit_up_ai_review:LimitUpAiReviewCollector"},
    run_params=("trade_date",),
    converters={"trade_date": date.fromisoformat},
),
```

runner 的任务参数白名单从 `TASK_SPECS` 派生，参数只在声明表维护一处；
管理后台"采集任务"页（目录 API `GET /admin/collector/tasks/catalog`）亦从 TASK_SPECS 派生，
API/UI 禁止另行硬编码任务清单。

### 3.2 多渠道 fallback

`_run_collector_for_task` 按 `resolve_channels_for_task` 返回的优先级顺序逐个尝试：

- 渠道未启用 / 该任务无对应采集器 → 记录日志，跳到下一个
- **仅 `FAILED` 触发轮换下一渠道**；`SUCCESS` / `PARTIAL` 立即返回
- **`SKIPPED` 是良性终态**（非交易日、已生成、无数据等），不轮换、不改写为 FAILED
- 全渠道失败 → FAILED，其余渠道的错误合并进 `result.errors`，并写 `collector_dead_letter` 死信

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
| `kline_base.py` | `sina_kline`（ths_kline 已下线：其接口实走东财 push2his 路径，被 WAF 封死） |
| `auction_base.py` | `sina_auction` / `ths_auction` |
| `sector_fund_flow_base.py` | `eastmoney_sector_fund_flow` / `ths_sector_fund_flow` |

新增同类渠道优先复用 / 扩展这些基类，禁止复制粘贴字段映射逻辑。

### 4.3 重存储编排（stores/）

`stores/` 承载需要复杂文件 / 元数据 / 多步写入的采集：

- `financial_report_store.py` — 东财结构化 + 巨潮 PDF 双源；下载 PDF 入 COS（S3 兼容），元数据写 `file_metadata`，触发 AI 摘要时回写 `summary` 列
- `research_report_store.py` — 东财研报下载；通过 `curl_cffi` 模拟 Chrome TLS 指纹绕过 `pdf.dfcfw.com` 的 WAF

> 同样写入 collector_log，但走自己的事务边界（不经过 `get_db`）。

## 5. 解析与容错约定

- **解析函数只用 `core.parsing`**：`to_optional_str` / `to_float` / `parse_cn_amount` / `clean_stock_code` / `parse_date` / `parse_time` — 禁止在 spider 内重复定义
- **akshare 容错**：空数据（`df is None or df.empty`）返回 `[]`；异常向上传播以便 fallback 生效
- **HTTP 客户端**：统一走 `core.http_client` 限流客户端（超时/重试/间隔）。东财 WAF 按 **TLS 指纹 + 路径 + 主机**限流（非 IP 封禁）：`push2` 高频连发按主机封禁 → 批量拉取走 `push2delay` 镜像；`push2his` kline 路径封死 → K 线一律走新浪；TLS 指纹敏感接口用 `curl_cffi` Chrome 指纹
- **日期参数**：默认值必须是 `latest_trading_day()`，禁止 `today_cn()`/`now` 兜底——周末手动补跑会静默空采；仅"天然只有当日"的数据（auction 快照、新浪分钟线）可用当日
- **日志**：入口调用 `core.logging.configure_logging()`，禁止 `logging.basicConfig`；任务日志自动携带 `task_run_id` / `task` / `source`
- **配置**：用 `core.config`（委托 `app.core.config`），禁止新增环境变量读取点
- **时区**：业务日期用 `app.core.clock`，Celery 调度一律按 Asia/Shanghai 书写

## 6. 容错与监控

```
容错与监控
  ├── collector_log（PostgreSQL，runner 唯一写入点）
  │     ├── task_run_id / task / source / status / 数据量
  │     ├── started_at / finished_at / errors[] / traceback / celery_task_id
  │     └── 每次执行一条记录，便于按任务/渠道/日期审计
  │
  ├── 多渠道 fallback（仅 FAILED 轮换；SKIPPED 良性终态）
  │
  ├── Celery 自动重试
  │     ├── ReviewInputDataNotReadyError（上游数据未就绪，如涨停池延迟）
  │     │     → self.retry(countdown=600, max_retries=3) 10 分钟退避
  │     └── SKIPPED 不重试（良性终态）
  │
  ├── collector_dead_letter 死信表（全渠道失败落库，可管理端查看/重放）
  │
  └── 调度自愈：beat 周期同步 collector_task 表，改行即生效无需重启
```

`runner.run_task` 是 `collector_log` 的**唯一写入点**：
- 生成 `task_run_id` 绑定 structlog 上下文
- 成功 / 部分成功 / 失败 / 跳过 各自写入对应 `status`
- 异常时记录 traceback，避免 collector_log 与 worker/cli/scf_handler 多处写入造成口径分裂

## 7. 后续文档索引

- [01-data-source.md](./01-data-source.md) — 数据源与反爬策略
- [03-data-storage.md](./03-data-storage.md) — 数据库设计与命名约定
- [04-ai-agent.md](./04-ai-agent.md) — AI Agent 体系（采集 → Skill 数据工具）
- [06-deployment.md](./06-deployment.md) — 部署架构与运维
