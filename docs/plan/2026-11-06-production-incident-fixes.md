# 生产事故修复清单（2026-11-06）

来源：2026-11-06 线上事故复盘。线上主机与工作目录为仓外配置（仓库变量 `DEPLOY_HOST` / `DEPLOY_PATH`），本文不写真实值。
本文档是本次修复的唯一台账，每修完一项勾选并补验证证据。

## 代码修复进度总览

| 项 | 状态 | 代码 | 单测 |
|---|---|---|---|
| P0-1 Beat 调度重建丢运行态 | ✅ 已修 | `backend/collector/celery_beat.py` | `tests/unit/collector/test_celery_beat.py`（11 passed） |
| P0-2 缺 broker visibility_timeout | ✅ 已修 | `backend/collector/celery_app.py` + `app/core/config.py` + `collector/core/config.py` | `tests/unit/collector/test_celery_app.py`（18 passed） |
| P0-3 anthropic 结构化输出方法序 | ✅ 已修 | `backend/app/agent/runtime/structured.py` | `tests/unit/agent/test_structured.py`（24 passed） |
| P1-4 结构化输出无校验修复回路 | ✅ 已修 | 同上 | 同上 |
| P1-5 采集失败不触发重试/死信 | ✅ 已修 | `backend/collector/celery_tasks.py` | `tests/unit/collector/test_celery_tasks.py`（19 passed） |

全量：`uv run pytest -m unit` → 3363 passed；`uv run ruff check .` → All checks passed；
`uv run mypy app/` → Success（`collector/` 下 13 处报错均为既有、与本次改动无关）。

**未完成**：线上部署、交易 Agent 模型绑定、failover 冷却窗口、港股 K 线启用（见文末非代码项）。

## 背景：2026-11-06 发生了什么

kimi（`llm_config.id=1`）**周额度耗尽**（返回 `You've reached your weekly (7-day) usage limit`），
两个交易 Agent 的 `trading_agent.llm_config_id=1` 都绑在它上面，只能落到备用配置 Minimax（config 2）；
而 Minimax 走 anthropic 协议时，`json_schema` 优先路径间歇性烧满 thinking 预算不吐 tool call，
报 `模型未返回结构化输出（tool call 缺失）`——该错误不被 `classify_llm_error` 识别，主备切换不触发，重试无效。

叠加两个调度层缺陷：

1. **Beat 重建条目丢运行态** → 19:30 交易计划等定时槽位被静默跳过（见 P0-1）。
2. **缺 `broker_transport_options.visibility_timeout`** → 超 1h 的任务被重复投递，heavy 队列堆积（见 P0-2）。

---

## P0-1 Beat 调度重建条目丢运行态，定时槽位被静默跳过

**状态**：✅ 已修（代码 + 单测，线上待部署验证）

### 现象

- 2026-11-06 19:30 beat **一条 dispatch 都没有**（11-04 / 11-05 同一时刻各有 8 条）。
  beat 日志在 `19:25:00` 与 `19:35:00` 之间只有一个空 tick。
- `agent_daily_plan_1900`（cron `30 19 * * 1-5`）当天完全没跑。
- 影响面：`collector_task` 40 条活跃 cron 里 **27 条是单分钟写法**
  （`0 16 * * 1-5`、`30 19 * * 1-5`、`35 11 * * 1-5` …），命中即当天不跑。

### 根因（已用 celery 5.6 源码 + 线上日志实锤）

1. celery 5.6 `Scheduler.sync_every = 180s`，而 beat 唤醒间隔 ≤ `max_interval = 300s`
   → **每次唤醒后都会触发 sync**。
2. `backend/collector/celery_beat.py` 的 `_load_schedules()` 每次都**新建** `ScheduleEntry`，
   `last_run_at` 被重置为 sync 时刻，`total_run_count` 归零。
3. celery `Service.start` 的循环顺序是 `tick → sleep → sync → tick`：
   **同一秒内 sync 先于 tick**，所以刚重建的条目直接参与当次判定。
4. crontab 语义实测（celery 5.6）：

   | `last_run_at` | 判定时刻 | `is_due` |
   |---|---|---|
   | `11-05 19:30` | `11-06 19:30` | `True` |
   | `11-06 19:25` | `11-06 19:30` | `True` |
   | `11-06 19:30:01` | `11-06 19:30:02` | **`False`**（顺延到次日） |
   | `11-06 19:31` | `11-06 19:35` | **`False`** |

   → 只要 sync 落点落在 `[槽位分钟, 槽位分钟+1min)`，该槽位当天整组任务不跑。

### 修法

`backend/collector/celery_beat.py::_load_schedules()`

- 重建时**沿用旧 entry 的 `last_run_at` / `total_run_count`**；
  仅当 cron 表达式 / args / options 真正变更时才新建 entry（变更后 `last_run_at = now` 才是正确语义）。
- `sync()` 补一条 info 日志（当前完全静默，无法审计同步次数与落点）。

### 验证

- 单测：同一 schedule 连续两次 `_load_schedules()`，`last_run_at` 不被重置；
  schedule 变更时 `last_run_at` 重置为新值。
  → `tests/unit/collector/test_celery_beat.py::TestScheduleEntryRunState`（4 条新增，全绿）。
- 线上：改完后观察一个非 `*/5` 的单分钟任务（如 `0 16 * * 1-5`）是否连续多日按时触发。
  → **待部署后观察**。

---

## P0-2 缺 `broker_transport_options.visibility_timeout`，长任务被重复投递

**状态**：✅ 已修（代码 + 单测，线上待部署验证）

### 现象

- 11-05 `hk-kline` 跑了 3840s；`collector.heavy` 队列积压 601 条。
- `collector/celery_app.py` 开了 `task_acks_late=True` + `task_reject_on_worker_lost=True`，
  但没设 `broker_transport_options` → kombu 默认 `visibility_timeout = 3600s`
  < 全局硬超时 `task_time_limit = 4800s` → 跑超 1h 的任务会被 broker 重新投递，队列陷入重复投递楔锁。

### 修法

`backend/collector/celery_app.py::make_celery_app()` 的 `app.conf.update(...)` 增加：

```python
broker_transport_options={"visibility_timeout": 7200},
```

必须大于全局硬超时 4800s。

### 验证

- 单测：`app.conf.broker_transport_options["visibility_timeout"] > app.conf.task_time_limit`。
  → `tests/unit/collector/test_celery_app.py::TestBrokerVisibilityTimeout`（已加）。
- 线上：`hk-kline` 是否按日更新、`collector.heavy` 积压是否回落。→ **待部署后观察**。

---

## P0-3 anthropic 协议结构化输出「json_schema 优先」致 Minimax 不吐 tool call

**状态**：✅ 已修（代码 + 单测，线上待部署验证）

### 现象

`app/agent/runtime/structured.py::_output_methods()` 对 anthropic 协议返回
`("json_schema", "function_calling")`，json_schema 优先。

Minimax 强制 adaptive thinking，thinking 与输出共享 `max_tokens` 预算，
间歇性烧满后不吐 tool call → `OutputParserException: 模型未返回结构化输出（tool call 缺失）`。
该错误 `classify_llm_error` 不认 → 不触发主备切换，重试也救不回来。

实测：Minimax + `method="function_calling"` 能稳定产出 `PaperTradeReviewDraft`（`stop_reason=tool_use`）。

### 修法

`backend/app/agent/runtime/structured.py`

- `_output_methods()`：anthropic 协议改为 `function_calling` 优先、`json_schema` 兜底；
  openai 协议仍只有 `function_calling`。
- **按端点记住实际生效的方法**（`_ENDPOINT_PREFERRED_METHOD`，键 `(config_id, model_name)`）：
  某端点哪种法生效，下次直接走它——kimi 忽略强制 tool_choice，撞一次
  `json_schema` 后会稳定落到 `function_calling`，不必每次都先烧一次失败法。
- thinking 不可关的端点把输出预算从 32768 提到 65536
  （`STRUCTURED_THINKING_MAX_TOKENS`）——thinking 与输出共享 `max_tokens`，
  预算不够时 Minimax 长思考烧满额度后只吐空 tool call。

### 验证

- 单测：anthropic 协议的方法序断言；端点方法记忆（首轮失败后下轮直接走生效法）。
  → `tests/unit/agent/test_structured.py`（24 passed）。
- 线上：kimi 恢复前，`agent_daily_plan` / `paper-trade-review` 能在 Minimax 上跑通。
  → **待部署后观察**。

---

## P1-4 结构化输出没有「校验失败修复」回路

**状态**：✅ 已修（代码 + 单测，线上待部署验证）

### 现象

`structured.py::_invoke()` 捕获 `ValidationError` 后只是换兜底方法重试，
**不把 pydantic 报错回喂给模型**。实测出现过 tool call 缺 `trades` 等必填字段 → 直接失败。

### 修法

`backend/app/agent/runtime/structured.py`

- `_invoke()` 捕获 `ValidationError` 后，把校验错误摘要（截断 2000 字符）
  追加到原提示（`_repair_message()`），让模型带着错误重出一次结构化结果；
  修复轮仍失败则照常上抛。
- 修复轮与「换兜底方法」两路各自成对：先在首选法上修复一次，
  首选法拿不到结构化输出再换兜底法，兜底法上同样有一次修复机会。

### 验证

- 单测：首轮缺必填字段 → 第二轮提示含校验错误与缺失字段名 → 成功。
  → `tests/unit/agent/test_structured.py::test_validation_error_triggers_repair_prompt`。

---

## P1-5 采集器失败不触发 Celery 重试 / 死信

**状态**：✅ 已修（代码 + 单测，线上待部署验证）

### 现象

`backend/collector/runtime/registry.py` 把采集异常吞成 `CollectResult(status=FAILED)` 正常返回
→ `collector/celery_tasks.py::run_collector_task` 视为成功 → **不重试、不进死信**
（`collector_log` 里记了 FAILED，但 Celery 侧没有任何重试动作）。

### 修法

`backend/collector/celery_tasks.py::run_collector_task`

- 采集结果为 `CollectStatus.FAILED` 时抛 `CollectorTaskFailedError`，
  交给 Celery 的重试 / 死信机制处理（此前失败只落在 `collector_log` 一行，
  Celery 侧记为成功，无任何补救动作）。
- 重试策略复用队列声明：次数取 `max_retries`，倒计时按 `retry_backoff`
  **指数退避**、封顶 `retry_backoff_max`（此前 `retry_backoff_max` 声明了
  却无人消费）；软超时路径同步改用同一退避函数。
- 重试耗尽后异常上抛，由既有 `LogAwareTask.on_failure` 写死信（约定不变）。
- `PARTIAL` / `SKIPPED` 不触发重试：部分成功与非交易日跳过都不是失败。

### 验证

- 单测：采集失败 → 进入重试（倒计时 30s / 最多 3 次）；重试耗尽 → 异常上抛走死信；
  `PARTIAL`/`SKIPPED` 不重试；退避递增与封顶。
  → `tests/unit/collector/test_celery_tasks.py::TestFailedResultRetry` /
  `::TestRetryCountdown`（6 条新增，全绿）。

---

## 非代码项（需用户决策 / 运维动作）

| 项 | 现状 | 建议 |
|---|---|---|
| 线上部署 | 线上镜像 `main-486c8d3`(2026-10-31)，HEAD `c7b3c19`；两个 failover 提交已在 `origin/develop`，线上容器尚无 `app/agent/skills/skill_failover.py`。**本次 5 项代码修复已完成、待部署** | 本批代码修完一并部署 |
| 交易 Agent 模型绑定 | 两个 Agent 的 `llm_config_id=1`(kimi) 周额度耗尽 | 改绑 config 8(mimo) 或其他健康配置 |
| failover 冷却窗口 | `settings.llm_failover_cooldown_seconds=600`，远短于上游周额度窗口 | 按错误类型区分（429 额度类长冷却，5xx 短冷却） |
| 港股 K 线 | `hk-kline` id 201 `is_active=f`，无自动更新 | 恢复启用 |
| 采集日志可观测性 | `collector_log.task_name` 存的是 task_type 而非实例名；校准类槽位不留记录 | 低优先级，后续处理 |

---

## 部署后验证清单

1. **beat 调度**：连续 2 个交易日核对单分钟 cron 任务（如 `0 16 * * 1-5`）
   是否每天都有 dispatch；beat 日志应出现 `beat_schedule_synced`（此前完全静默）。
2. **采集失败可观测**：`collector_dead_letter` 表应开始出现 FAILED 任务的死信记录。
3. **长任务不重投**：观察 `collector.heavy` 队列积压是否回落、`hk-kline` 是否有重复 dispatch。
4. **结构化输出**：交易 Agent 的复盘/计划任务日志里 `method` 字段应记 `function_calling`；
   若某端点仍失败，看 `meta.method` 判定是否需要端点级方法序。
