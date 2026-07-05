# 数据采集引擎架构（腾讯云 SCF Job 版）

## 1. 采集引擎总览

本系统采用**腾讯云函数 SCF Job 函数**替代传统 Celery Worker 模式。
每个采集任务独立打包为 Docker 镜像，由 Timer 定时触发器驱动，异步执行后自动销毁。

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        腾讯云 SCF — Job 函数集群                            │
│                                                                            │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐ │
│  │ Timer: 交易日16:00│  │ Timer: 每日 8:00  │  │ Timer: 每30分钟          │ │
│  │ Cron: 0 16 * * 1-5│ │ Cron: 0 8 * * *   │  │ Cron: 0/30 * * * *       │ │
│  └────────┬─────────┘  └────────┬─────────┘  └────────────┬─────────────┘ │
│           │                     │                          │               │
│  ┌────────┴─────────┐  ┌────────┴──────────┐  ┌───────────┴─────────────┐ │
│  │ collect-kline     │  │ collect-report    │  │ collect-news            │ │
│  │ ENV: kline        │  │ ENV: financial    │  │ ENV: news               │ │
│  │ Memory: 4096MB    │  │ Memory: 4096MB    │  │ Memory: 2048MB          │ │
│  │ Timeout: 900s     │  │ Timeout: 1800s    │  │ Timeout: 300s           │ │
│  └────────┬──────────┘  └────────┬──────────┘  └───────────┬─────────────┘ │
│           │                     │                          │               │
│  ┌────────┴──────────┐  ┌───────┴──────────┐                              │
│  │ collect-research   │  │ collect-auction  │   ... 按需新增 Job 函数      │
│  │ ENV: research      │  │ ENV: auction     │                              │
│  │ Timer: 每日9,18时   │  │ Timer: 盘前9:15   │                              │
│  └────────┬───────────┘  └────────┬─────────┘                              │
│           │                      │                                         │
│           └──────────┬───────────┘                                         │
│                      ▼                                                     │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │              collector 镜像 (Dockerfile.collector)                  │   │
│  │                                                                     │   │
│  │   entrypoint-collector.sh → python -m collector.tasks $COLLECT_TASK │   │
│  │                                                                     │   │
│  │   包含: Scrapy 异步引擎 + akshare 接口 + Playwright 浏览器          │   │
│  └─────────────────────────────────┬───────────────────────────────────┘   │
│                                    │                                       │
│          ┌─────────────────────────┼─────────────────────────┐             │
│          ▼                         ▼                         ▼             │
│  ┌──────────────┐        ┌──────────────────┐       ┌──────────────┐      │
│  │  请求中间件    │        │   数据清洗管道     │       │   数据分发器   │      │
│  │  IP代理池     │        │  去重→标准化→校验  │       │  PG/ES/MinIO  │      │
│  │  Cookie池    │        │                   │       │  /Milvus      │      │
│  │  限速器      │        └──────────────────┘       └──────────────┘      │
│  └──────────────┘                                                         │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                        轻量服务器（数据存储层）
                        PostgreSQL / ES / MinIO / Milvus
```

## 2. 为什么用 SCF Job 替代 Celery

| 维度 | Celery Worker 方案 | SCF Job 函数方案 |
|------|-------------------|-----------------|
| **运行模式** | 常驻进程，持续等待任务 | 按需触发，执行完销毁 |
| **成本** | 服务器 24h 运行费用 | 仅按执行时长计费 |
| **扩展性** | 需手动增减 Worker 数量 | 云函数自动弹性伸缩 |
| **维护** | 需维护 Celery + Redis 队列 | 腾讯云托管，零运维 |
| **适合场景** | 高频率、低延迟任务 | 定时批量采集任务 |
| **资源利用** | CPU 空闲时浪费 | 无任务时不消耗资源 |
| **任务隔离** | 共享进程空间 | 每个 Job 独立容器 |

> **结论**：对于每日/每小时的定时批量采集，SCF Job 函数是更优选择。无需常驻进程，成本更低。

## 3. 采集器设计

### 3.1 基础采集器抽象

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional
from datetime import datetime
import asyncio
import random


class CollectStatus(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class CollectResult:
    source: str
    data_type: str
    status: CollectStatus
    items_collected: int
    items_stored: int
    errors: list[str]
    started_at: datetime
    finished_at: datetime
    metadata: dict[str, Any]


class BaseCollector(ABC):
    """采集器基类 — 所有采集 Job 的父类"""

    def __init__(self, config: dict):
        self.config = config
        self.proxy_pool = None
        self.cookie_pool = None

    @abstractmethod
    async def collect(self, **kwargs) -> list[dict]:
        """执行采集，返回原始数据"""
        ...

    @abstractmethod
    async def validate(self, data: dict) -> bool:
        """单条数据校验"""
        ...

    @abstractmethod
    async def transform(self, raw: dict) -> dict:
        """数据转换/标准化"""
        ...

    async def store(self, items: list[dict]) -> int:
        """批量入库，返回入库条数"""
        raise NotImplementedError

    async def run(self, **kwargs) -> CollectResult:
        """完整采集流程（模板方法）"""
        started_at = datetime.now()
        errors = []
        try:
            raw_data = await self.collect(**kwargs)
            transformed = []
            for item in raw_data:
                try:
                    t = await self.transform(item)
                    if await self.validate(t):
                        transformed.append(t)
                except Exception as e:
                    errors.append(str(e))
            stored_count = await self.store(transformed)
            return CollectResult(
                source=self.config["source"],
                data_type=self.config["data_type"],
                status=CollectStatus.SUCCESS if not errors else CollectStatus.PARTIAL,
                items_collected=len(raw_data),
                items_stored=stored_count,
                errors=errors,
                started_at=started_at,
                finished_at=datetime.now(),
                metadata={}
            )
        except Exception as e:
            return CollectResult(
                source=self.config["source"],
                data_type=self.config["data_type"],
                status=CollectStatus.FAILED,
                items_collected=0, items_stored=0,
                errors=[str(e)],
                started_at=started_at, finished_at=datetime.now(),
                metadata={}
            )
```

### 3.2 各类采集器实现

```
                          ┌──────────────┐
                          │ BaseCollector │
                          └──────┬───────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          │                      │                      │
  ┌───────┴────────┐  ┌─────────┴────────┐  ┌─────────┴────────┐
  │ API 采集器      │  │ Web 爬虫采集器    │  │ 文件下载采集器     │
  │ (行情/资金流)   │  │ (公告/新闻)       │  │ (PDF财报/研报)    │
  └───────┬────────┘  └─────────┬────────┘  └─────────┬────────┘
          │                      │                      │
  ┌───────┴────────┐  ┌─────────┴────────┐  ┌─────────┴────────┐
  │ THSKline       │  │ CninfoCollector  │  │ PDFDownloader    │
  │ EastMoneyFlow  │  │ SinaNewsCollector│  │ ReportParser     │
  └────────────────┘  └──────────────────┘  └──────────────────┘
```

### 3.3 巨潮资讯采集器（核心）

```python
class CninfoCollector(WebCrawlerCollector):
    """巨潮资讯财报/公告采集器"""

    BASE_URL = "https://www.cninfo.com.cn"

    async def collect(self, stock_codes: list[str],
                      start_date: str, end_date: str) -> list[dict]:
        """采集指定公司的定期报告和公告"""
        results = []
        async with aiohttp.ClientSession() as session:
            # 模拟登录
            await self._login(session)
            
            for code in stock_codes:
                page = 1
                while True:
                    items = await self._fetch_disclosure_list(
                        session, code, start_date, end_date, page
                    )
                    if not items:
                        break
                    results.extend(items)
                    page += 1
                    await asyncio.sleep(random.uniform(3, 8))  # 反爬间隔
        return results

    async def download_report_pdf(self, session, adjunct_url: str) -> bytes:
        """下载财报 PDF"""
        resp = await session.get(
            f"{self.BASE_URL}{adjunct_url}",
            headers={"Referer": self.BASE_URL}
        )
        return await resp.read()

    async def store(self, items: list[dict]) -> int:
        """数据入库：元数据入 PG，PDF 入 MinIO"""
        count = 0
        for item in items:
            # 1. 结构化元数据 → PostgreSQL
            await self.db.execute("""
                INSERT INTO file_metadata 
                (file_path, original_name, file_type, stock_code, report_date)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (file_path) DO NOTHING
            """, ...)
            
            # 2. PDF 文件 → MinIO
            pdf_bytes = await self.download_report_pdf(item["pdf_url"])
            await self.minio.put_object(
                bucket="financial-reports",
                object_name=f"{item['stock_code']}/{item['date']}_{item['type']}.pdf",
                data=pdf_bytes
            )
            count += 1
        return count
```

## 4. 定时调度策略（SCF Timer 触发器）

每个采集任务在腾讯云控制台配置独立的 Timer 触发器：

```
┌─────────────────────────────────────────────────────────────────┐
│                    采集任务调度矩阵                               │
├──────────────────┬──────────────────┬──────────┬───────────────┤
│ 任务名称          │ Cron 表达式       │ 内存     │ 说明           │
├──────────────────┼──────────────────┼──────────┼───────────────┤
│ collect-kline    │ 0 16 * * 1-5     │ 4096MB   │ 交易日盘后K线   │
│ collect-auction  │ 15,25 9 * * 1-5  │ 2048MB   │ 集合竞价        │
│ collect-fundflow │ 0 17 * * 1-5     │ 2048MB   │ 资金流向        │
│ collect-report   │ 0 8 * * *        │ 4096MB   │ 财报(财报季密集) │
│ collect-research │ 0 9,18 * * *     │ 4096MB   │ 研报每日早晚     │
│ collect-news     │ 0/30 * * * *     │ 2048MB   │ 新闻每30分钟     │
│ collect-weekly   │ 0 10 * * 5       │ 2048MB   │ 周K线/周报      │
└──────────────────┴──────────────────┴──────────┴───────────────┘
```

**环境变量驱动**：所有 Job 共用同一个 `collector` 镜像，通过 `COLLECT_TASK` 环境变量区分：

```bash
# K线采集 Job 函数的环境变量
COLLECT_TASK=kline
DB_HOST=<轻量服务器IP>
DB_PORT=5432
DB_USER=investor
DB_PASSWORD=xxx
DB_NAME=investment_db
REDIS_HOST=<轻量服务器IP>
ES_HOST=<轻量服务器IP>
MINIO_HOST=<轻量服务器IP>
MILVUS_HOST=<轻量服务器IP>
# ... 其他连接配置
```

## 5. 中间件层

### 5.1 请求中间件

```python
class RequestMiddleware:
    """请求中间件：代理轮换、Cookie维护、限速"""

    def __init__(self):
        # 代理池：使用付费代理服务，通过 API 获取可用 IP
        self.proxy_pool = ProxyPool(
            provider_url=os.getenv("PROXY_POOL_URL")
        )
        # Cookie 池：多账号轮换，定期刷新登录态
        self.cookie_pool = CookiePool(
            accounts=json.loads(os.getenv("CNINFO_ACCOUNTS", "[]"))
        )
        # 限速器：简单令牌桶，避免触发反爬
        self.rate_limiters: dict[str, RateLimiter] = {}

    async def process_request(self, request: dict) -> dict:
        source = request.get("source", "default")
        
        # 1. 限速
        limiter = self.rate_limiters.setdefault(source, RateLimiter())
        await limiter.acquire()
        
        # 2. 代理轮换
        proxy = await self.proxy_pool.get()
        if proxy:
            request["proxy"] = proxy
        
        # 3. Cookie 注入
        cookie = await self.cookie_pool.get(source)
        if cookie:
            request["headers"]["Cookie"] = cookie
        
        # 4. 随机 User-Agent
        request["headers"]["User-Agent"] = random.choice(UA_LIST)
        
        return request
```

### 5.2 数据清洗管道

```python
class DataPipeline:
    """数据清洗管道 — 所有采集 Job 共用"""

    def __init__(self):
        self.steps = [
            DeduplicateStep(),     # 基于 composite key 去重
            NormalizeStep(),       # 字段类型/格式标准化
            ValidateStep(),        # 必填字段/范围校验
            EnrichStep(),          # 数据补全（如行业分类标签）
        ]

    async def process(self, items: list[dict]) -> list[dict]:
        for step in self.steps:
            items = await step.run(items)
        return items
```

## 6. 入口脚本（entrypoint-collector.sh）

```bash
#!/bin/bash
# docker/entrypoint-collector.sh
# SCF Job 函数入口 — 根据 $COLLECT_TASK 路由到不同采集逻辑

set -e

TASK="${COLLECT_TASK:-kline}"
echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Starting collector job: $TASK"

cd /app

case "$TASK" in
    kline)
        python -m collector.tasks collect_kline --period daily
        ;;
    auction)
        python -m collector.tasks collect_auction
        ;;
    fund-flow)
        python -m collector.tasks collect_fund_flow
        ;;
    financial-report)
        python -m collector.tasks collect_financial_report
        ;;
    research)
        python -m collector.tasks collect_research
        ;;
    news)
        python -m collector.tasks collect_news
        ;;
    *)
        echo "ERROR: Unknown task: $TASK"
        exit 1
        ;;
esac

echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Job $TASK completed successfully"
```

## 7. 容错与监控

由于 SCF Job 是云托管服务，监控方案与自建 Celery 不同：

```
监控策略：
  ├── SCF 云监控（腾讯云内置）
  │     ├── 函数调用次数 / 错误次数
  │     ├── 执行耗时 (平均/P99)
  │     ├── 内存使用率
  │     └── 并发执行次数
  │
  ├── 应用层日志
  │     ├── 每次 Job 执行写入 PostgreSQL 日志表
  │     └── 采集量统计（当日入库条数、失败条数）
  │
  └── 告警
        ├── SCF 错误率 > 5% → 企业微信/钉钉通知
        └── 连续 3 次执行失败 → 暂停触发器，人工介入

失败重试：
  ├── SCF 异步重试（内置，最多重试2次）
  └── 下一次 Timer 触发自动覆盖（增量采集天然容错）
```
