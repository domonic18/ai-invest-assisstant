# 数据库设计与存储方案

## 1. 存储架构全景

```
┌──────────────────────────────────────────────────────────────────┐
│                        存储分层架构                                │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              应用缓存层 (Redis)                               │ │
│  │  热点数据 │ Session │ Celery broker │ 分布式锁                │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                     │
│  ┌───────────────────────────┴─────────────────────────────────┐ │
│  │              结构化存储层 (PostgreSQL + TimescaleDB)           │ │
│  │  公司信息 │ 财务数据 │ 交易行情 │ 产业链版本 │ 用户与配置      │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                     │
│  ┌───────────────────────────┴─────────────────────────────────┐ │
│  │              全文检索层 (Elasticsearch)                       │ │
│  │  公告全文 │ 新闻内容 │ 搜索建议                                │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                     │
│  ┌───────────────────────────┴─────────────────────────────────┐ │
│  │              文件存储层 (COS · S3 兼容)                        │ │
│  │  财报 PDF │ 研报 PDF │ 公告 PDF │ pg_dump 备份                │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

## 2. 命名约定（关键）

后端数据库已完成统一命名重构，新增 / 重命名表与字段必须遵循以下约定（`docker/database/init-scripts/01-schema.sql` + `migrations/20260722_schema_refactor.sql`）：

- **表名结构**：`<分类前缀>_<数据类型>_<标的类型>[_<粒度/子类型>]`，市场级数据可省略 `<标的类型>`
- **分类前缀**
  - 行情数据：`quote_`（如 `quote_kline_stock_daily`、`quote_auction_index`、`quote_kline_index_daily`）
  - 资金流向：`capital_`（如 `capital_fund_flow_stock`、`capital_fund_flow_sector`）
  - 市场情绪：`market_`（如 `market_breadth`、`market_amount`）
  - 股池：`pool_`（如 `pool_limit_up_stock`、`pool_limit_down_stock`、`pool_dragon_tiger_stock`）
  - 财务报表：`financial_`（如 `financial_balance_sheet`、`financial_income_statement`、`financial_cash_flow_statement`）
  - 产业链：`industry_chain_`
  - 成分/映射：`mapping_`（如 `mapping_stock_concept`、`mapping_index_stock`）
- **字段名**：完整单词优先，禁用无上下文缩写；同一语义统一用同一单词（涨跌幅一律 `change_pct`）
- **约束 / 索引命名**：`pk_<table>` / `uq_<table>_<columns>` / `fk_<table>_<ref_table>` / `idx_<table>_<columns>` / `chk_<table>_<column>`
- **审计字段**：业务表统一使用 `created_at` / `updated_at`

## 3. 核心表清单（按业务域）

### 3.1 基础信息域

| 表 | 说明 |
|----|------|
| `stock_basic` | 股票 / 公司基础信息（含申万一二三级行业、上市日期、股本） |
| `mapping_stock_concept` | 股票 ↔ 概念板块映射（东财概念成分股采集写入） |
| `mapping_index_stock` | 指数成分股 |

### 3.2 行情域（TimescaleDB 超表）

| 表 | 说明 |
|----|------|
| `quote_kline_stock_daily` / `_weekly` / `_monthly` | 个股日 / 周 / 月 K 线 |
| `quote_kline_index_daily` | 指数日 K（沪深 300 / 上证 50 / 创业板指 / 富时 A50） |
| `quote_kline_etf_daily` | ETF 日 K（沪深 300 ETF 系列） |
| `quote_minute_stock` | 个股分钟线 |
| `quote_minute_index` | 指数分钟线 |
| `quote_auction_index` | 指数集合竞价成交额（Tushare `stk_auction` 聚合） |
| `quote_spot_index` | 指数 spot 快照 |
| `quote` | 个股实时行情快照 |

### 3.3 资金流向域

| 表 | 说明 |
|----|------|
| `capital_fund_flow_stock` | 个股资金流（超大 / 大 / 中 / 小单净流入） |
| `capital_fund_flow_sector` | 板块资金流（行业 / 概念，含 `change_pct`） |

### 3.4 市场情绪 / 股池域

| 表 | 说明 |
|----|------|
| `market_breadth` | 市场宽度（涨家数 / 跌家数 / 涨停 / 跌停） |
| `market_amount` | 上交所 / 深交所成交流水（用于复盘成交额趋势） |
| `pool_limit_up_stock` | 涨停股池（东财官方池，含首次封板 / 最后封板时间 / 封板次数 / 一字 T 字推导） |
| `pool_limit_down_stock` | 跌停股池 |
| `pool_dragon_tiger_stock` | 龙虎榜 |
| `pool_broken_stock` | 炸板池 |

### 3.5 财务域

| 表 | 说明 |
|----|------|
| `financial_balance_sheet` | 资产负债表 |
| `financial_income_statement` | 利润表 |
| `financial_cash_flow_statement` | 现金流量表 |
| `file_metadata` | PDF 文件元数据，新增 `summary` JSONB 列缓存 AI 摘要（首次生成后命中缓存，避免重复调用 LLM） |
| `ipo_info` | IPO 信息 |
| `fund_holding` | 基金十大重仓股 |

### 3.6 产业链域（版本化）

| 表 | 说明 |
|----|------|
| `industry_chain_version` | 产业链分析版本（行业 / 输入快照 / 任务运行 ID / 创建人 / 备注） |
| `industry_chain_node` | 节点（环节名 / 类型 / 关键公司 / 财务摘要） |
| `industry_chain_edge` | 边（上下游关系 / 强度） |
| `industry_chain_company_mapping` | 公司 ↔ 环节映射（基于经营范围自下而上推导） |
| `ai_analysis_result` | AI 分析结果通用表（含 input_hash，相同输入命中缓存） |

### 3.7 AI 复盘域

| 表 | 说明 |
|----|------|
| `market_review_base` | 共享底稿（系统生成的三段式 AI 大盘综述） |
| `user_market_review` | 用户级覆盖（用户在底稿基础上的编辑，section 级合并） |

> AI 复盘改为 YAML 声明式分区（`prompts/skills/market-daily-review.yaml`），section 级编辑时只重生成被改动的分区，未改动分区直接复用底稿。

### 3.8 用户 / 系统域

| 表 | 说明 |
|----|------|
| `users` | 用户（首个注册用户自动晋升 admin） |
| `user_settings` | 用户级设置（涨跌配色方案 / K 线均线 MA 列表） |
| `watchlist` | 自选股 |
| `assistant_session` | AI 助手会话（LangChain Agent Protocol 线程/运行持久化） |
| `collector_task` | 采集任务定义（task_type / cron / queue / 启用），**调度唯一真相源** |
| `collector_channel_config` | 渠道级配置（source / base_url / api_key / extra） |
| `collector_channel_data_type` | 渠道 × 数据类型优先级关联表 |
| `collector_log` | 采集执行日志（runner 唯一写入点，含 `celery_task_id`） |
| `collector_dead_letter` | 采集死信（全渠道失败落库，管理端可查看/重放） |
| `llm_config` | LLM 配置（provider / model / api_key 加密存储） |

## 4. Elasticsearch 索引设计

```json
{
  "settings": {
    "number_of_shards": 3,
    "number_of_replicas": 1,
    "analysis": {
      "analyzer": {
        "cn_analyzer": { "type": "custom", "tokenizer": "ik_max_word", "filter": ["lowercase"] }
      }
    }
  },
  "mappings": {
    "properties": {
      "id":            { "type": "keyword" },
      "stock_code":    { "type": "keyword" },
      "title":         { "type": "text", "analyzer": "cn_analyzer", "fields": { "keyword": { "type": "keyword" } } },
      "content":       { "type": "text", "analyzer": "cn_analyzer" },
      "doc_type":      { "type": "keyword" },
      "publish_date":  { "type": "date" },
      "source":        { "type": "keyword" },
      "url":           { "type": "keyword" },
      "sentiment":     { "type": "float" },
      "keywords":      { "type": "keyword" },
      "industry_tags": { "type": "keyword" }
    }
  }
}
```

## 5. 对象存储（COS · S3 兼容）

```
{bucket}/                              # invest-files
├── financial-reports/                # 财报 PDF
│   └── {stock_code}/
│       └── {report_date}_{report_type}.pdf
├── research-reports/                 # 研报 PDF
│   └── {broker}/
│       └── {stock_code}_{date}_{title}.pdf
├── announcements/                    # 公告 PDF
│   └── {stock_code}/
│       └── {date}_{announcement_id}.pdf
└── backups/                          # pg_dump 定时备份
```

- 应用经 S3 兼容 SDK（`minio_service` 封装）读写，仅改 endpoint + 密钥即可在 S3 兼容存储间切换
- 下载走预签名 URL，前端不直连存储
- `file_metadata.summary` 缓存 AI 摘要，列表 / 详情接口直接返回，避免重复 LLM 调用
- 研报 PDF 下载用 `curl_cffi` 模拟 Chrome TLS 指纹绕过 `pdf.dfcfw.com` 的 WAF（httpx 会被 JS 反爬页拦截）

## 6. Redis 缓存设计

| 缓存类型 | Key Pattern | TTL | 说明 |
|----------|-------------|-----|------|
| 实时行情 | `quote:{stock_code}` | 5min | 最新成交价 / 涨跌幅 |
| K 线缓存 | `kline:{stock_code}:{period}:latest` | 1h | 最近 K 线 |
| 热门股票 | `hot_stocks:daily` | 1d | 当日热门 |
| 产业链图 | `chain:{industry_l1}` | 24h | 产业链图谱缓存 |
| Session | `session:{session_id}` | 24h | 用户登录会话 |
| 限流 | `ratelimit:{user_id}` | 1min | API 限流计数 |
| AI 生成锁 | `redis_lock`（`app.core.locking`） | 300s | 防止定时任务与手动触发并发双跑 LLM |
| Celery broker | `collector.realtime` / `batch` / `heavy` | - | kombu List，beat/dispatcher 投递、worker 消费 |

## 7. 迁移管理

- 全量初始化脚本：`docker/database/init-scripts/`（`01-schema.sql` / `02-indexes.sql` / `03-seed.sql`）
- 增量迁移：`docker/database/migrations/` 下按日期归档的 SQL（如 `20260722_schema_refactor.sql`、`20260829_limit_up_ai_review_task.sql`），幂等可重复执行
- 新增字段时**同时**更新 init-scripts（新部署）+ 写一条带日期前缀的 migration（已部署环境），历史上已四例漂移，须严守

## 8. 后续文档索引

- [00-overview.md](./00-overview.md) — 总体架构与目录结构
- [02-data-collection.md](./02-data-collection.md) — 采集引擎架构
- [04-ai-agent.md](./04-ai-agent.md) — AI Agent 体系（产业链版本化、AI 复盘）
- [backend/CLAUDE.md](../../backend/CLAUDE.md) — 仓储层与事务边界规范
