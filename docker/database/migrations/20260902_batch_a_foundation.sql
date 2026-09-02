-- 批次 A 数据底座：全球指标日行情 / 跟踪指数配置 / 投资日历 / 财联社电报（幂等可重复执行）
-- quote_global_index_daily + tracked_index_config：A2 全球指标与工作台跟踪指数
-- calendar_event：A3 投资日历（FOMC/BLS 权威日程种子随后续迁移/03-seed 写入）
-- news_telegraph：A1 财联社电报（驻留进程增量轮询，v1 仅 PG 不入 ES）

-- ============================================================
-- A2: 全球指数/指标日行情（COMEX 黄金、美元指数、美债收益率等）
-- ============================================================

CREATE TABLE IF NOT EXISTS quote_global_index_daily (
    index_code    VARCHAR(16)   NOT NULL,
    trade_date    DATE          NOT NULL,
    open          DECIMAL(16,4),
    high          DECIMAL(16,4),
    low           DECIMAL(16,4),
    close         DECIMAL(16,4),
    change_pct    DECIMAL(12,4),
    volume        BIGINT,
    amount        DECIMAL(20,2),
    source        VARCHAR(50),
    created_at    TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (index_code, trade_date)
);

SELECT create_hypertable('quote_global_index_daily', 'trade_date', chunk_time_interval => INTERVAL '1 year', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_quote_global_index_daily_code_date
    ON quote_global_index_daily(index_code, trade_date DESC);

-- ============================================================
-- A2: 跟踪指数配置（工作台/行情卡展示清单，Admin CRUD 管理）
-- ============================================================

CREATE TABLE IF NOT EXISTS tracked_index_config (
    id               BIGSERIAL PRIMARY KEY,
    index_code       VARCHAR(16)  NOT NULL,
    index_name       VARCHAR(100) NOT NULL,
    market_category  VARCHAR(10)  NOT NULL CONSTRAINT chk_tracked_index_config_market_category
                     CHECK (market_category IN ('A股', '全球')),
    data_source      VARCHAR(50)  NOT NULL,
    sort_order       INT          NOT NULL DEFAULT 100,
    is_enabled       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_tracked_index_config_index_code UNIQUE (index_code)
);

-- 默认 8 项：4 A 股指数（新浪）+ 4 全球指标（东财/tushare）
INSERT INTO tracked_index_config (index_code, index_name, market_category, data_source, sort_order, is_enabled)
VALUES
    ('sh000001', '上证指数',       'A股', 'sina',      1, true),
    ('sz399001', '深证成指',       'A股', 'sina',      2, true),
    ('sz399006', '创业板指',       'A股', 'sina',      3, true),
    ('sh000688', '科创50',         'A股', 'sina',      4, true),
    ('GC00Y',    'COMEX 黄金',     '全球', 'eastmoney', 5, true),
    ('DXY',      '美元指数',       '全球', 'eastmoney', 6, true),
    ('US2Y',     '美债 2Y 收益率', '全球', 'tushare',   7, true),
    ('US10Y',    '美债 10Y 收益率', '全球', 'tushare',  8, true)
ON CONFLICT (index_code) DO NOTHING;

-- ============================================================
-- A3: 投资日历事件（FOMC/BLS 官方日程等）
-- ============================================================

CREATE TABLE IF NOT EXISTS calendar_event (
    id              BIGSERIAL PRIMARY KEY,
    event_time      TIMESTAMPTZ  NOT NULL,
    end_time        TIMESTAMPTZ,
    title           VARCHAR(300) NOT NULL,
    category        VARCHAR(20)  NOT NULL CONSTRAINT chk_calendar_event_category
                    CHECK (category IN ('宏观', '央行动态', '新股', '解禁', '财报', '会议')),
    impact_markets  VARCHAR(50)[],
    source          VARCHAR(50),
    source_url      VARCHAR(1000),
    related_symbols TEXT[],
    source_hash     VARCHAR(32)  NOT NULL,          -- md5(source|event_time|title)，幂等键
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_calendar_event_source_hash UNIQUE (source_hash)
);

CREATE INDEX IF NOT EXISTS idx_calendar_event_time ON calendar_event(event_time);
CREATE INDEX IF NOT EXISTS idx_calendar_event_category_time ON calendar_event(category, event_time);

-- ============================================================
-- A1: 财联社电报（stream 驻留进程 10s 增量轮询，cls_msg_id 幂等）
-- ============================================================

CREATE TABLE IF NOT EXISTS news_telegraph (
    id            BIGSERIAL PRIMARY KEY,
    cls_msg_id    BIGINT       NOT NULL,
    title         VARCHAR(500),
    content       TEXT,
    category      VARCHAR(50),                       -- cls type 字段原值
    importance    SMALLINT,                          -- cls level 字段
    shared        SMALLINT,
    stock_codes   TEXT[],
    extra         JSONB,                             -- 其余 cls 字段（brief/shareurl 等）
    publish_time  TIMESTAMPTZ  NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_news_telegraph_cls_msg_id UNIQUE (cls_msg_id)
);

CREATE INDEX IF NOT EXISTS idx_news_telegraph_publish_time ON news_telegraph(publish_time DESC);

-- ============================================================
-- 采集任务与渠道关联
-- ============================================================

-- 防御性补齐 eastmoney/tushare 渠道的 global-index 数据类型（渠道已存在时）
UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["global-index"]'::jsonb
WHERE source IN ('eastmoney', 'tushare')
  AND NOT supported_data_types @> '["global-index"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT c.id, d.data_type, 1
FROM collector_channel_config c
CROSS JOIN (VALUES ('global-index')) AS d(data_type)
WHERE c.source IN ('eastmoney', 'tushare')
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- cls 渠道（签名自持无需 api_key，入目录便于管理）
INSERT INTO collector_channel_config (source, name, is_enabled, supported_data_types)
VALUES ('cls', '财联社', true, '["cls-telegraph-backfill"]'::jsonb)
ON CONFLICT (source) DO NOTHING;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'cls-telegraph-backfill', 1
FROM collector_channel_config
WHERE source = 'cls'
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- 渠道解析按 TaskSpec.name 匹配 collector_channel_data_type.data_type，
-- 同一任务类型的多条调度行（实时/收盘/美债）镜像 index-auction 的多行模式
INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES
    -- 盘中半小时级实时快照（COMEX 黄金/美元指数，push2delay 镜像）
    ('eastmoney_global_index_realtime', 'global-index', 'eastmoney', '*/30 9-17 * * 1-5', true),
    -- 美股收盘定盘兜底（北京时间 6/7 点覆盖美夏/冬令时收盘）
    ('eastmoney_global_index_close', 'global-index', 'eastmoney', '0 6,7 * * 2-6', true),
    -- 美债收益率日度（us_tycr 单次返回全量历史，upsert 幂等）
    ('tushare_us_yield_daily', 'global-index', 'tushare', '30 6 * * 2-6', true),
    -- cls 电报历史回补：手动触发不排 cron，增量由 stream 驻留进程负责
    ('cls_telegraph_backfill', 'cls-telegraph-backfill', 'cls', NULL, false)
ON CONFLICT (task_name) DO UPDATE
SET task_type = EXCLUDED.task_type, source = EXCLUDED.source;
