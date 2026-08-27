# Collector 高可靠采集架构改造方案

## 背景与目标

当前 `collector` 容器内跑的是**单进程、单 asyncio 事件循环**的 worker，调度器（APScheduler）与队列消费者（Redis `BRPOP`）共处一室。`sina_quote` 等 spider 在 `async def collect()` 里直接调用同步的 `akshare`/`requests`/`pandas`，一旦网络挂起就会阻塞整个事件循环，导致所有队列任务持续 `pending`、调度器停摆。

本次改造目标：将采集系统迁移到 **Celery + Redis**，实现：

- 任务间真正隔离，单个任务挂起只影响一个 worker 子进程；
- 硬超时 + 自动重试 + 死信队列；
- 调度器独立运行，从 `collector_task` 表读取 cron；
- 多队列分级，可按队列独立扩缩容；
- 复用现有 `CollectorLog` / `CollectorTask` 表与任务注册表 `TASK_SPECS`；
- 管理后台 API、CLI、SCF handler 保持兼容；
- **新增任务（如行业热点新闻爬取）仅通过配置扩展，不改动执行框架代码**。

> 已确认选择：**直接完整迁移到 Celery**，**调度器使用 Celery Beat 读表**，**不引入 Flower，仅用日志 + Prometheus 指标**。

---

## 1. 设计原则

1. **配置驱动，避免硬编码业务逻辑**
   - 任务名称、队列、超时、重试、调度 cron 全部来自 `TASK_SPECS` 与 `collector_task` 表；
   - Celery 任务体只认识 `{"task": "xxx", ...}`，不感知具体业务含义。

2. **可扩展**
   - 新增一种采集任务只需：在 `TASK_SPECS` 增加一条声明 → 实现 spider → 可选在 `collector_task` 加调度；
   - 队列分级按任务属性（实时性、重量、数据源）自动路由，无需改 worker 命令。

3. **不过度设计**
   - 不用 Flower，用日志 + 最少必要 Prometheus 指标；
   - 不用复杂的工作流引擎，Celery task + queue 足够；
   - 保留现有 `run_task` 执行路径，不大改 spider 接口。

---

## 2. 目标架构

```
                    ┌─────────────────┐
  Web Admin API ───▶│  dispatcher     │
  CLI/SCF    ──────▶│  (Celery task)  │
                    └────────┬────────┘
                             │ apply_async(queue=..., timeout=...)
                    ┌────────▼────────┐
                    │   Redis broker  │  (DB 1)
                    │   Redis result  │  (DB 2)
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
┌───────▼────────┐  ┌────────▼────────┐  ┌───────▼────────┐
│  worker-realtime│  │  worker-batch   │  │  worker-heavy  │
│  -Q collector.  │  │  -Q collector.  │  │  -Q collector. │
│   realtime      │  │   batch         │  │   heavy        │
└─────────────────┘  └─────────────────┘  └─────────────────┘
        │
┌───────▼────────┐
│   celery-beat   │  ◀── 读取 collector_task.schedule
│   (custom DB    │      生成 crontab 触发 Celery task
│    scheduler)   │
└─────────────────┘
```

---

## 3. 队列分级策略（配置驱动）

队列不是按任务名硬编码，而是按 `TaskSpec` 的元数据自动推导：

```python
# backend/collector/runtime/registry.py
@dataclass(frozen=True)
class TaskSpec:
    name: str
    data_type: str
    collectors: dict[str, str]
    queue: Literal["realtime", "batch", "heavy"] = "batch"  # 新增
    soft_time_limit: int | None = None   # 秒，None 表示用队列默认值
    max_retries: int | None = None       # None 表示用队列默认值
    config_params: tuple[str, ...] = ()
    run_params: tuple[str, ...] = ()
    defaults: dict[str, Any] = field(default_factory=dict)
    converters: dict[str, Callable[[Any], Any]] = field(default_factory=dict)
```

队列默认策略：

| 队列 | 默认任务特征 | 并发 | soft/hard limit | 默认重试 |
|------|-------------|------|-----------------|----------|
| `collector.realtime` | 高频、轻量、交易时间运行 | 4 | 60s / 120s | 3 次，退避 30s |
| `collector.batch` | 日终批量、中等数据量 | 2 | 300s / 600s | 3 次，退避 60s |
| `collector.heavy` | PDF、大文件、长周期回填 | 1 | 1800s / 3600s | 2 次，退避 300s |
| `collector.eastmoney` | 来源为 eastmoney 且需限流 | 1 | 同 batch | 同 batch |

队列解析逻辑封装在 `collector/celery_app.py::resolve_queue(task_name, preferred_source)`：

1. 若 `CollectorTask.queue` 有覆盖，优先使用；
2. 否则若 `preferred_source == "eastmoney"` 且 `TaskSpec` 未显式指定队列，路由到 `collector.eastmoney`；
3. 否则使用 `TaskSpec.queue`；
4. 最终兜底 `collector.batch`。

新增任务（如 `industry-hot-news`）只需在 `TASK_SPECS` 声明 `queue="realtime"`，无需改 Celery 代码。

---

## 4. 新增与修改文件

### 4.1 新增模块

| 文件 | 职责 |
|------|------|
| `backend/collector/celery_app.py` | Celery app 工厂、队列/路由/序列化配置、`resolve_queue()`、`worker_process_init` 信号 |
| `backend/collector/celery_tasks.py` | 单一通用 Celery task `run_collector_task`，负责调用 `run_task`、超时捕获、死信写入 |
| `backend/collector/celery_beat.py` | `CollectorDatabaseScheduler` 从 `collector_task` 加载 cron |
| `backend/collector/core/async_helpers.py` | `run_in_thread()` 线程池辅助 |
| `backend/app/models/collector_dead_letter.py` | 死信表模型 |
| `docker/database/migrations/20260827_celery_collector.sql` | 表结构变更 |

### 4.2 修改模块

| 文件 | 修改内容 |
|------|----------|
| `backend/collector/runtime/registry.py` | `TaskSpec` 增加 `queue`、`soft_time_limit`、`max_retries`；为现有任务填默认值；来源限流逻辑不硬编码任务名 |
| `backend/collector/runtime/runner.py` | `run_task` 接收 `celery_task_id` 并写入 `CollectorLog.meta`；软超时内写失败状态 |
| `backend/collector/runtime/dispatcher.py` | 默认走 Celery `apply_async`，队列/超时/重试由 `resolve_queue()` 与 `TaskSpec` 决定；保留 `COLLECTOR_USE_LEGACY_QUEUE` 开关作为回滚 |
| `backend/collector/runtime/worker.py` | 标记 deprecated，保留到割接后删除 |
| `backend/collector/runtime/scheduler.py` | 标记 deprecated，保留到割接后删除 |
| `backend/app/models/collector_log.py` | 增加 `celery_task_id` 列（indexed） |
| `backend/app/models/collector_task.py` | 增加可选 `queue` 列 |
| `backend/app/schemas/collector.py` | `CollectorRunResponse` 增加 `celery_task_id` |
| `backend/app/schemas/collector_task.py` | 增加 `queue` 字段 |
| `backend/app/api/v1/admin/collector.py` | 响应增加 `celery_task_id`；新增 `/logs/{log_id}/celery-status`；新增 `/dead-letters` 分页 |
| `backend/app/api/v1/admin/tasks.py` | `CollectorTaskUpdate` 支持更新 `queue` |
| `backend/collector/spiders/sina_quote.py` | `ak.stock_zh_a_spot()` → `run_in_thread()` |
| `backend/collector/spiders/sina_index_spot.py` | `ak.stock_zh_index_spot_sina()` → `run_in_thread()` |
| `backend/collector/spiders/sina_market_breadth.py` | `ak.stock_zh_a_spot()` → `run_in_thread()` |
| `backend/collector/core/http_client.py` | `time.sleep(delay)` → `asyncio.sleep(delay)`；保留限流器 |
| `backend/app/services/minio_service.py` | 同步 MinIO 方法 → `asyncio.to_thread()` |
| `backend/app/services/knowledge_base_service.py` | `pypdf` 提取 → `asyncio.to_thread()` |
| `docker/collector/entrypoint-collector.sh` | 支持 `celery-beat` / `celery-worker` 模式 |
| `docker-compose.yml` | 新增 `celery-beat`、`celery-worker-realtime/batch/heavy`；移除原 `collector`；加 healthcheck |

---

## 5. 数据库变更

```sql
-- docker/database/migrations/20260827_celery_collector.sql
ALTER TABLE collector_log
    ADD COLUMN celery_task_id VARCHAR(64) NULL,
    ADD CONSTRAINT uq_collector_log_celery_task_id UNIQUE (celery_task_id);
CREATE INDEX idx_collector_log_celery_task_id ON collector_log(celery_task_id);
CREATE INDEX idx_collector_log_status_started_at ON collector_log(status, started_at DESC);
CREATE INDEX idx_collector_log_task_name ON collector_log(task_name);

ALTER TABLE collector_task
    ADD COLUMN queue VARCHAR(20) NULL;
CREATE INDEX idx_collector_task_active_schedule ON collector_task(is_active, schedule) WHERE is_active = TRUE;

CREATE TABLE collector_dead_letter (
    id SERIAL PRIMARY KEY,
    task_name VARCHAR(100) NOT NULL,
    source VARCHAR(50) NULL,
    payload JSONB NOT NULL,
    celery_task_id VARCHAR(64) NULL,
    collector_log_id INT NULL,
    error_msg TEXT NULL,
    retry_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_collector_dead_letter_task_name ON collector_dead_letter(task_name);
CREATE INDEX idx_collector_dead_letter_created_at ON collector_dead_letter(created_at DESC);
```

---

## 6. Celery 配置要点

`backend/collector/celery_app.py` 核心配置：

```python
app = Celery("collector")
app.conf.update(
    broker_url=settings.celery_broker_url,
    result_backend=settings.celery_result_backend,
    task_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    task_default_queue="collector.batch",
)

# 注册队列
app.conf.task_queues = (
    Queue("collector.realtime"),
    Queue("collector.batch"),
    Queue("collector.heavy"),
    Queue("collector.eastmoney"),
)
```

`run_collector_task` 任务签名：

```python
@app.task(
    bind=True,
    base=LogAwareTask,  # 捕获 SoftTimeLimitExceeded 写日志
)
def run_collector_task(self, payload: dict[str, Any]) -> dict[str, Any]:
    configure_logging()
    payload = payload.copy()
    payload["celery_task_id"] = self.request.id
    result = asyncio.run(run_task(payload))
    return result.to_dict()
```

具体 `soft_time_limit` / `max_retries` / `default_retry_delay` 不在装饰器硬编码，而在 dispatch 时通过 `apply_async(..., soft_time_limit=..., max_retries=..., retry_backoff=...)` 动态传入，来源同样是 `TaskSpec`。

---

## 7. 调度器：Celery Beat + DatabaseScheduler

`backend/collector/celery_beat.py::CollectorDatabaseScheduler`：

1. `setup_schedule()` 加载 `collector_task` 中 `is_active = TRUE` 且 `schedule IS NOT NULL` 的行；
2. 每行生成一个 Celery beat entry：
   ```python
   {
       "task": "collector.celery_tasks.run_collector_task",
       "schedule": crontab(...),
       "args": ({"task": row.task_type, "preferred_source": row.source},),
       "options": {
           "queue": resolve_queue(row.task_type, row.source),
       },
   }
   ```
3. `sync()` 每 60s 热重载；
4. 任务完成后更新 `collector_task.last_run_at / last_status / last_error`。

新增调度任务只需在 `collector_task` 表插入一行，无需改 Beat 代码。

---

## 8. 任务执行与日志流

1. 管理后台 / CLI / SCF 调用 `dispatch_collector_task`；
2. Dispatcher 插入 `CollectorLog(status="pending")`，拿到 `log.id`；
3. 通过 `resolve_queue()` 得到队列，通过 `TaskSpec` 得到 soft_time_limit / max_retries；
4. 调用 `run_collector_task.apply_async(...)`；
5. 将 Celery `task_id` 写入 `collector_log.celery_task_id`；
6. Worker 子进程执行 `asyncio.run(run_task(payload))`；
7. `run_task` 标记 `running`，完成后写终态；
8. 重试耗尽后 Celery 任务进入死信，写入 `collector_dead_letter`。

---

## 9. 同步阻塞代码处理

prefork 已隔离跨任务影响，但为保持 worker 内协同及 CLI/SCF 安全，统一通过线程池包装：

```python
# backend/collector/core/async_helpers.py
import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial

_executor: ThreadPoolExecutor | None = None

def get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="collector_sync")
    return _executor

async def run_in_thread(func, /, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(get_executor(), partial(func, *args, **kwargs))
```

首批包装清单：

| 位置 | 处理 |
|------|------|
| `backend/collector/spiders/sina_quote.py` | `ak.stock_zh_a_spot()` → `run_in_thread()` |
| `backend/collector/spiders/sina_index_spot.py` | `ak.stock_zh_index_spot_sina()` → `run_in_thread()` |
| `backend/collector/spiders/sina_market_breadth.py` | `ak.stock_zh_a_spot()` → `run_in_thread()` |
| `backend/collector/core/http_client.py` | `time.sleep` → `asyncio.sleep` |
| `backend/app/services/minio_service.py` | 同步 MinIO 调用 → `asyncio.to_thread()` |
| `backend/app/services/knowledge_base_service.py` | `pypdf` 提取 → `asyncio.to_thread()` |

其余 spider 在后续迭代中逐步包装，不阻塞本次架构迁移。

---

## 10. 扩展性设计：如何新增一种任务

以“行业热点新闻爬取”为例，新增任务只需三步：

1. **实现 spider**（遵循现有 `BaseCollector` 接口）：
   ```python
   # backend/collector/spiders/industry_hot_news.py
   class IndustryHotNewsCollector(BaseCollector): ...
   ```

2. **在 `TASK_SPECS` 增加声明**：
   ```python
   TaskSpec(
       name="industry-hot-news",
       data_type="industry_hot_news",
       collectors={"sina": "collector.spiders.industry_hot_news:IndustryHotNewsCollector"},
       queue="realtime",          # 自动进入 collector.realtime 队列
       soft_time_limit=60,
       max_retries=3,
   )
   ```

3. **（可选）在管理后台添加定时调度**：在 `collector_task` 表插入 `task_type="industry-hot-news"`、`schedule="*/5 9-15 * * 1-5"`。

无需修改 Celery task、worker 命令、Beat 代码、dispatcher 逻辑。

---

## 11. 监控与告警（最小必要）

不使用 Flower，通过 Celery 信号自埋点 Prometheus 指标：

| 指标 | 说明 |
|------|------|
| `collector_queue_length{queue}` | Redis 队列长度 |
| `collector_tasks_total{status,queue,task_name}` | 任务终态计数 |
| `collector_task_duration_seconds{queue,task_name}` | 执行耗时 histogram |
| `collector_task_retries_total{task_name}` | 重试次数 |
| `collector_dead_letter_total{task_name}` | 死信计数 |

告警规则：

- `collector.realtime` 队列深度 > 100 持续 5 分钟；
- 最近 5 分钟新增死信；
- worker 心跳丢失 > 2 分钟；
- heavy 队列 30 分钟成功率 < 90%。

---

## 12. Docker Compose 变更

移除单一 `collector` 服务，新增：

- `celery-beat`
- `celery-worker-realtime`
- `celery-worker-batch`
- `celery-worker-heavy`

worker 命令示例：

```bash
celery -A collector.celery_app worker \
  -Q collector.realtime \
  -n realtime@%h \
  -P prefork \
  --concurrency=4 \
  --prefetch-multiplier=1 \
  --max-tasks-per-child=200
```

healthcheck：

```bash
celery -A collector.celery_app inspect ping -t 5 || exit 1
```

---

## 13. 迁移步骤

1. **Schema 变更**（零停机）：执行 SQL migration；
2. **代码准备**：新增 Celery 模块，修改 registry/dispatcher/runner/models/schemas/API；
3. **本地验证**：
   ```bash
   uv run celery -A collector.celery_app beat --scheduler collector.celery_beat:CollectorDatabaseScheduler
   uv run celery -A collector.celery_app worker -Q collector.realtime -n realtime@%h -P prefork --concurrency=2
   uv run python -m collector.runtime.cli quote --preferred-source sina
   ```
4. **部署**：更新 `docker-compose.yml`，替换为 Celery 服务；
5. **清理**：稳定两周后删除旧 `worker.py` / `scheduler.py` / `queue.py` 及 legacy 开关。

---

## 14. 验证清单

- [ ] `uv run mypy app/ collector/` 通过；
- [ ] `uv run ruff check .` 通过；
- [ ] `uv run pytest -m unit` 通过；
- [ ] 新增单元测试：Celery task wrapper、DatabaseScheduler cron 解析、dispatcher 路由；
- [ ] 新增集成测试：Redis broker + worker 子进程执行 dummy task；
- [ ] 本地触发 `quote`、`financial-report`、`sector-fund-flow`，确认队列/日志/死信行为；
- [ ] 部署后三个 worker 均响应 `inspect ping`；
- [ ] Prometheus 指标正常上报。

---

## 15. 风险与应对

| 风险 | 应对 |
|------|------|
| Prefork 子进程继承父进程 SQLAlchemy engine | `worker_process_init` dispose engine；`pool_pre_ping=True` |
| akshare/pandas 内存泄漏 | `max-tasks-per-child` 限制子进程任务数 |
| EastMoney 多 worker 并发冲垮 IP | 单独 `collector.eastmoney` 队列，`concurrency=1` |
| Celery payload 含非 JSON 类型 | dispatcher 统一转 ISO 字符串 |
| 软/硬超时 kill 前未写 DB | `SoftTimeLimitExceeded` handler 先标记 `CollectorLog` |
| Beat 单点故障 | `restart: unless-stopped` + 健康检查；不运行多 Beat |
| 重试导致重复入库 | 依赖现有 upsert/conflict key；`CollectorLog` 按 `celery_task_id` 去重 |

---

## 16. 待确认事项

- 是否按本方案直接实施完整 Celery 迁移？
- 是否需要先重启线上卡死的 `investment-collector-1` 容器，让队列在改造前恢复消费？
