# 数据库设计与存储方案

## 1. 存储架构全景

```
┌──────────────────────────────────────────────────────────────────┐
│                        存储分层架构                                │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              应用缓存层 (Redis)                               │ │
│  │  热点数据 │ Session │ 实时行情缓存 │ 采集任务队列              │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                     │
│  ┌───────────────────────────┴─────────────────────────────────┐ │
│  │              结构化存储层 (PostgreSQL + TimescaleDB)           │ │
│  │  公司信息 │ 财务数据 │ 交易行情 │ 产业链关系 │ 用户信息        │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                     │
│  ┌───────────────────────────┴─────────────────────────────────┐ │
│  │              全文检索层 (Elasticsearch)                       │ │
│  │  公告全文 │ 新闻内容 │ 研报摘要 │ 搜索建议                    │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                     │
│  ┌───────────────────────────┴─────────────────────────────────┐ │
│  │              文件存储层 (MinIO)                                │ │
│  │  财报 PDF │ 研报 PDF │ 公告 PDF │ 图片附件                    │ │
│  └───────────────────────────┬─────────────────────────────────┘ │
│                              │                                     │
│  ┌───────────────────────────┴─────────────────────────────────┐ │
│  │              向量知识库 (Milvus)                               │ │
│  │  PDF 文档向量 │ 财务指标向量 │ 产业链节点语义向量              │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

## 2. PostgreSQL 核心表设计

### 2.1 基础信息域

```sql
-- 股票/公司基础信息
CREATE TABLE stock_basic (
    id              BIGSERIAL PRIMARY KEY,
    stock_code      VARCHAR(10) NOT NULL,        -- 股票代码 000001
    stock_name      VARCHAR(50) NOT NULL,        -- 股票名称 平安银行
    market          VARCHAR(4) NOT NULL,         -- 市场: sh/sz/bj
    industry_l1     VARCHAR(50),                 -- 申万一级行业
    industry_l2     VARCHAR(50),                 -- 申万二级行业
    industry_l3     VARCHAR(50),                 -- 申万三级行业
    listing_date    DATE,                        -- 上市日期
    total_shares    BIGINT,                      -- 总股本
    circulating_shares BIGINT,                   -- 流通股本
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(stock_code, market)
);

CREATE INDEX idx_stock_code ON stock_basic(stock_code);
CREATE INDEX idx_industry_l1 ON stock_basic(industry_l1);
```

### 2.2 交易行情域（TimescaleDB 超表）

```sql
-- 启用 TimescaleDB 扩展
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- K线行情表（转化为超表）
CREATE TABLE kline_daily (
    stock_code      VARCHAR(10) NOT NULL,
    trade_date      DATE NOT NULL,
    open            DECIMAL(12,3),
    high            DECIMAL(12,3),
    low             DECIMAL(12,3),
    close           DECIMAL(12,3),
    volume          BIGINT,                     -- 成交量（手）
    amount          DECIMAL(20,2),              -- 成交额（元）
    amplitude       DECIMAL(8,2),               -- 振幅%
    pct_change      DECIMAL(8,2),               -- 涨跌幅%
    turnover_rate   DECIMAL(8,2),               -- 换手率%
    
    PRIMARY KEY(stock_code, trade_date)
);

SELECT create_hypertable('kline_daily', 'trade_date');
CREATE INDEX idx_kline_code_date ON kline_daily(stock_code, trade_date DESC);

-- 集合竞价数据
CREATE TABLE auction_data (
    id              BIGSERIAL PRIMARY KEY,
    stock_code      VARCHAR(10) NOT NULL,
    trade_date      DATE NOT NULL,
    match_time      TIME NOT NULL,              -- 竞价时间点
    price           DECIMAL(12,3),              -- 匹配价格
    volume          BIGINT,                     -- 匹配量
    bid_prices      DECIMAL(12,3)[],            -- 买盘报价数组
    bid_volumes     BIGINT[],                   -- 买盘量数组
    ask_prices      DECIMAL(12,3)[],            -- 卖盘报价数组
    ask_volumes     BIGINT[],                   -- 卖盘量数组
    
    UNIQUE(stock_code, trade_date, match_time)
);

-- 资金流向
CREATE TABLE fund_flow (
    id              BIGSERIAL PRIMARY KEY,
    stock_code      VARCHAR(10) NOT NULL,
    trade_date      DATE NOT NULL,
    main_net_inflow     DECIMAL(20,2),          -- 主力净流入
    super_large_net     DECIMAL(20,2),          -- 超大单净流入
    large_net           DECIMAL(20,2),          -- 大单净流入
    medium_net          DECIMAL(20,2),          -- 中单净流入
    small_net           DECIMAL(20,2),          -- 小单净流入
    
    UNIQUE(stock_code, trade_date)
);

SELECT create_hypertable('fund_flow', 'trade_date');
```

### 2.3 财务数据域

```sql
-- 资产负债表
CREATE TABLE balance_sheet (
    id                  BIGSERIAL PRIMARY KEY,
    stock_code          VARCHAR(10) NOT NULL,
    report_date         DATE NOT NULL,             -- 报告期
    report_type         VARCHAR(10) NOT NULL,      -- 年报/半年报/季报
    -- 资产
    total_assets        DECIMAL(20,2),             -- 总资产
    current_assets      DECIMAL(20,2),             -- 流动资产
    cash_equivalents    DECIMAL(20,2),             -- 货币资金
    accounts_receivable DECIMAL(20,2),             -- 应收账款
    inventory           DECIMAL(20,2),             -- 存货
    fixed_assets        DECIMAL(20,2),             -- 固定资产
    intangible_assets   DECIMAL(20,2),             -- 无形资产
    goodwill            DECIMAL(20,2),             -- 商誉
    -- 负债
    total_liabilities   DECIMAL(20,2),             -- 总负债
    current_liabilities DECIMAL(20,2),             -- 流动负债
    long_term_debt      DECIMAL(20,2),             -- 长期借款
    -- 权益
    total_equity        DECIMAL(20,2),             -- 总权益
    paid_in_capital     DECIMAL(20,2),             -- 实收资本
    retained_earnings   DECIMAL(20,2),             -- 未分配利润
    
    UNIQUE(stock_code, report_date)
);

-- 利润表
CREATE TABLE income_statement (
    id                  BIGSERIAL PRIMARY KEY,
    stock_code          VARCHAR(10) NOT NULL,
    report_date         DATE NOT NULL,
    report_type         VARCHAR(10) NOT NULL,
    total_revenue       DECIMAL(20,2),             -- 营业收入
    operating_cost      DECIMAL(20,2),             -- 营业成本
    selling_expense     DECIMAL(20,2),             -- 销售费用
    admin_expense       DECIMAL(20,2),             -- 管理费用
    rd_expense          DECIMAL(20,2),             -- 研发费用
    finance_expense     DECIMAL(20,2),             -- 财务费用
    operating_profit    DECIMAL(20,2),             -- 营业利润
    net_profit          DECIMAL(20,2),             -- 归母净利润
    net_profit_deducted DECIMAL(20,2),             -- 扣非归母净利润
    eps                 DECIMAL(10,4),             -- 基本每股收益
    
    UNIQUE(stock_code, report_date)
);

-- 现金流量表
CREATE TABLE cash_flow_statement (
    id                      BIGSERIAL PRIMARY KEY,
    stock_code              VARCHAR(10) NOT NULL,
    report_date             DATE NOT NULL,
    report_type             VARCHAR(10) NOT NULL,
    cf_operations           DECIMAL(20,2),         -- 经营活动现金流
    cf_investing            DECIMAL(20,2),         -- 投资活动现金流
    cf_financing            DECIMAL(20,2),         -- 筹资活动现金流
    net_cash_flow           DECIMAL(20,2),         -- 净现金流
    free_cash_flow          DECIMAL(20,2),         -- 自由现金流
    
    UNIQUE(stock_code, report_date)
);

CREATE INDEX idx_financial_code_date ON income_statement(stock_code, report_date DESC);
```

### 2.4 产业链关系域

```sql
-- 产业链节点
CREATE TABLE industry_chain_node (
    id              BIGSERIAL PRIMARY KEY,
    node_name       VARCHAR(100) NOT NULL,        -- 节点名称
    industry_l1     VARCHAR(50),                  -- 所属一级行业
    node_type       VARCHAR(20) NOT NULL,         -- upstream/midstream/downstream
    description     TEXT,
    key_companies   BIGINT[],                     -- 关键公司 stock_basic.id
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 产业链关系
CREATE TABLE industry_chain_edge (
    id              BIGSERIAL PRIMARY KEY,
    source_node_id  BIGINT REFERENCES industry_chain_node(id),
    target_node_id  BIGINT REFERENCES industry_chain_node(id),
    relation_type   VARCHAR(50),                  -- 供应/加工/销售
    relation_desc   TEXT,
    strength        DECIMAL(5,2),                 -- 关系强度 0-100
    source          VARCHAR(50),                  -- 数据来源: agent/manual
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(source_node_id, target_node_id, relation_type)
);

-- 公司-产业链节点映射
CREATE TABLE company_chain_mapping (
    id              BIGSERIAL PRIMARY KEY,
    stock_code      VARCHAR(10) NOT NULL,
    chain_node_id   BIGINT REFERENCES industry_chain_node(id),
    position        VARCHAR(50),                  -- 公司在节点中的位置定位
    revenue_ratio   DECIMAL(8,4),                 -- 该业务收入占比
    confidence      DECIMAL(5,2),                 -- 置信度
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(stock_code, chain_node_id)
);
```

### 2.5 用户/系统域

```sql
-- 用户表
CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    username        VARCHAR(50) UNIQUE NOT NULL,
    email           VARCHAR(100) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(20) DEFAULT 'user',   -- user/admin/analyst
    is_active       BOOLEAN DEFAULT true,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 用户关注列表
CREATE TABLE user_watchlist (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT REFERENCES users(id),
    stock_code      VARCHAR(10) NOT NULL,
    tags            VARCHAR(50)[],                -- 用户自定义标签
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(user_id, stock_code)
);
```

## 3. Elasticsearch 索引设计

### 3.1 公告/新闻索引

```json
{
  "settings": {
    "number_of_shards": 3,
    "number_of_replicas": 1,
    "analysis": {
      "analyzer": {
        "cn_analyzer": {
          "type": "custom",
          "tokenizer": "ik_max_word",
          "filter": ["lowercase"]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "id": { "type": "keyword" },
      "stock_code": { "type": "keyword" },
      "stock_name": { "type": "keyword" },
      "title": {
        "type": "text",
        "analyzer": "cn_analyzer",
        "fields": {
          "keyword": { "type": "keyword" }
        }
      },
      "content": {
        "type": "text",
        "analyzer": "cn_analyzer"
      },
      "doc_type": { "type": "keyword" },
      "publish_date": { "type": "date" },
      "source": { "type": "keyword" },
      "url": { "type": "keyword" },
      "sentiment": { "type": "float" },
      "keywords": { "type": "keyword" },
      "industry_tags": { "type": "keyword" }
    }
  }
}
```

## 4. MinIO 文件存储

### 4.1 存储结构

```
minio-bucket/
├── financial-reports/          # 财报 PDF
│   └── {stock_code}/
│       └── {report_date}_{report_type}.pdf
├── research-reports/           # 研报 PDF
│   └── {broker}/
│       └── {stock_code}_{date}_{title}.pdf
├── announcements/              # 公告 PDF
│   └── {stock_code}/
│       └── {date}_{announcement_id}.pdf
└── images/                     # 图表截图
    └── {date}/
        └── {stock_code}_{chart_type}.png
```

### 4.2 文件元数据表

```sql
CREATE TABLE file_metadata (
    id              BIGSERIAL PRIMARY KEY,
    file_path       VARCHAR(500) NOT NULL UNIQUE,  -- MinIO 路径
    original_name   VARCHAR(500),                  -- 原始文件名
    file_type       VARCHAR(20) NOT NULL,          -- financial_report/research_report/announcement
    stock_code      VARCHAR(10),
    report_date     DATE,
    report_type     VARCHAR(20),
    broker          VARCHAR(100),                  -- 券商名称（研报专用）
    file_size       BIGINT,                        -- 文件大小 bytes
    md5_hash        VARCHAR(32),                   -- 文件 MD5
    download_url    VARCHAR(500),                  -- 预签名下载地址
    download_count  INT DEFAULT 0,
    upload_at       TIMESTAMPTZ DEFAULT NOW(),
    
    INDEX idx_file_type (file_type),
    INDEX idx_stock_report (stock_code, report_date)
);
```

## 5. Milvus 向量知识库

### 5.1 Collection 设计

```python
from pymilvus import Collection, CollectionSchema, FieldSchema, DataType

# 财报文档向量 Collection
financial_doc_chunks = Collection(
    name="financial_doc_chunks",
    schema=CollectionSchema([
        FieldSchema("id", DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema("stock_code", DataType.VARCHAR, max_length=10),
        FieldSchema("report_date", DataType.VARCHAR, max_length=10),
        FieldSchema("report_type", DataType.VARCHAR, max_length=20),
        FieldSchema("chunk_index", DataType.INT32),         # 切片序号
        FieldSchema("chunk_text", DataType.VARCHAR, max_length=4000),  # 文本内容
        FieldSchema("embedding", DataType.FLOAT_VECTOR, dim=1536),     # OpenAI embedding
        FieldSchema("file_path", DataType.VARCHAR, max_length=500),
        FieldSchema("page_number", DataType.INT32),         # PDF 页码
    ])
)

# 研报文档向量 Collection
research_doc_chunks = Collection(
    name="research_doc_chunks",
    schema=CollectionSchema([
        FieldSchema("id", DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema("stock_code", DataType.VARCHAR, max_length=10),
        FieldSchema("industry", DataType.VARCHAR, max_length=50),
        FieldSchema("broker", DataType.VARCHAR, max_length=100),
        FieldSchema("author", DataType.VARCHAR, max_length=100),
        FieldSchema("publish_date", DataType.VARCHAR, max_length=10),
        FieldSchema("rating", DataType.VARCHAR, max_length=20),   # 评级
        FieldSchema("chunk_text", DataType.VARCHAR, max_length=4000),
        FieldSchema("embedding", DataType.FLOAT_VECTOR, dim=1536),
        FieldSchema("file_path", DataType.VARCHAR, max_length=500),
    ])
)
```

### 5.2 PDF 处理管道

```
PDF 文件下载
    │
    ▼
PDF 解析 (PyMuPDF / pdfplumber)
    │
    ├──→ 文本提取 → 分块(Chunking) → Embedding → Milvus
    │
    └──→ 表格提取 → 结构化 → PostgreSQL (财务指标)
```

## 6. Redis 缓存设计

| 缓存类型 | Key Pattern | TTL | 说明 |
|----------|-------------|-----|------|
| 实时行情 | `quote:{stock_code}` | 5min | 最新成交价/涨跌幅 |
| K线缓存 | `kline:{stock_code}:{period}:latest` | 1h | 最近K线数据 |
| 热门股票 | `hot_stocks:daily` | 1d | 当日热门股票列表 |
| 产业链图 | `chain:{industry_l1}` | 24h | 产业链图谱缓存 |
| Session | `session:{session_id}` | 24h | 用户登录会话 |
| 限流 | `ratelimit:{user_id}` | 1min | API 限流计数 |
| 任务锁 | `lock:{task_name}` | 5min | 防止重复执行 |
