-- 迭代 2 监测分组数据扩展：FedWatch 概率 / 板块行情快照 / 二批跟踪指数（幂等可重复执行）
-- fed_watch_snapshot + fed_watch_probability：CME FedWatch 官方概率表每日快照（QuikStrike 直采）
-- quote_sector_daily：东财行业/概念板块收盘快照
-- tracked_index_config 增 7 行：港美股六指数 + 日债 10Y

-- ============================================================
-- FedWatch 概率快照元数据（数据时点 + 当前目标区间）
-- ============================================================

CREATE TABLE IF NOT EXISTS fed_watch_snapshot (
    as_of_date         DATE     NOT NULL,               -- CT 数据日期
    data_as_at         TIMESTAMPTZ NOT NULL,            -- 官网 "Data as of" CT 时刻（aware UTC）
    current_range_low  INT      NOT NULL,               -- 当前目标区间下限（bps）
    current_range_high INT      NOT NULL,               -- 当前目标区间上限（bps）

    PRIMARY KEY (as_of_date),
    CONSTRAINT chk_fed_watch_snapshot_range CHECK (current_range_low < current_range_high)
);

-- ============================================================
-- FedWatch 条件概率分布（每次会议 × 目标区间落位概率，官网口径直存）
-- ============================================================

CREATE TABLE IF NOT EXISTS fed_watch_probability (
    as_of_date   DATE         NOT NULL,
    meeting_date DATE         NOT NULL,
    range_low    INT          NOT NULL,
    range_high   INT          NOT NULL,
    probability  DECIMAL(6,3) NOT NULL,                 -- 0-100
    created_at   TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (as_of_date, meeting_date, range_low),
    CONSTRAINT chk_fed_watch_probability_value CHECK (probability >= 0 AND probability <= 100),
    CONSTRAINT chk_fed_watch_probability_range CHECK (range_low < range_high)
);

SELECT create_hypertable('fed_watch_probability', 'as_of_date', chunk_time_interval => INTERVAL '1 year', if_not_exists => TRUE);

-- ============================================================
-- 行业/概念板块收盘快照（东财 clist fs=m:90+t:2 / t:3，每日 16:05 批）
-- ============================================================

CREATE TABLE IF NOT EXISTS quote_sector_daily (
    sector_type       VARCHAR(16)  NOT NULL CONSTRAINT chk_quote_sector_daily_type
                      CHECK (sector_type IN ('industry', 'concept')),
    sector_code       VARCHAR(16)  NOT NULL,            -- 东财板块代码（BKxxxx）
    sector_name       VARCHAR(50)  NOT NULL,
    trade_date        DATE         NOT NULL,
    close             DECIMAL(16,4),
    change_pct        DECIMAL(12,4),
    amount            DECIMAL(20,2),                    -- 成交额（元）
    turnover_rate     DECIMAL(10,4),                    -- 换手率（%）
    up_count          INT,
    down_count        INT,
    leader_stock_name VARCHAR(50),
    source            VARCHAR(50),

    PRIMARY KEY (sector_type, sector_code, trade_date)
);

SELECT create_hypertable('quote_sector_daily', 'trade_date', chunk_time_interval => INTERVAL '1 year', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_quote_sector_daily_type_date
    ON quote_sector_daily(sector_type, trade_date DESC);

-- ============================================================
-- 跟踪指数二批：港美股六指数（东财 secid）+ 日债 10Y（日本财务省）
-- ============================================================

INSERT INTO tracked_index_config (index_code, index_name, market_category, data_source, sort_order, is_enabled)
VALUES
    ('HSI',    '恒生指数',       '全球', 'eastmoney', 9,  true),
    ('HSTECH', '恒生科技',       '全球', 'eastmoney', 10, true),
    ('DJIA',   '道琼斯',         '全球', 'eastmoney', 11, true),
    ('NDX',    '纳斯达克',       '全球', 'eastmoney', 12, true),
    ('SPX',    '标普500',        '全球', 'eastmoney', 13, true),
    ('N225',   '日经225',        '全球', 'eastmoney', 14, true),
    ('JP10Y',  '日本10Y国债',    '全球', 'mof',       15, true)
ON CONFLICT (index_code) DO NOTHING;

-- ============================================================
-- 渠道：mof / cme / yahoo（无鉴权直采）；eastmoney 补板块行情
-- ============================================================

INSERT INTO collector_channel_config (source, name, is_enabled, supported_data_types)
VALUES
    ('mof',   '日本财务省', true, '["global-index"]'::jsonb),
    ('cme',   '芝商所',     true, '["fed-watch"]'::jsonb),
    ('yahoo', 'Yahoo Finance', true, '["global-index"]'::jsonb)
ON CONFLICT (source) DO NOTHING;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT c.id, d.data_type, 1
FROM collector_channel_config c
JOIN (VALUES
    ('mof',   'global-index'),
    ('cme',   'fed-watch'),
    ('yahoo', 'global-index')
) AS d(source, data_type) ON d.source = c.source
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- 防御性补齐 eastmoney 渠道的 sector-quote 数据类型（渠道已存在时）
UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["sector-quote"]'::jsonb
WHERE source = 'eastmoney'
  AND NOT supported_data_types @> '["sector-quote"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'sector-quote', 1
FROM collector_channel_config
WHERE source = 'eastmoney'
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- ============================================================
-- 采集任务（小时均为北京时间）
-- ============================================================

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES
    -- 日债收益率日度（MOF 全量 CSV upsert 幂等，日本清晨发布前日终值）
    ('mof_jpy_yield_daily', 'global-index', 'mof', '30 7 * * 2-6', true),
    -- FedWatch 概率快照（美收盘结算后晨间采集，QuikStrike 三步会话）
    ('cme_fed_watch_daily', 'fed-watch', 'cme', '30 7 * * 2-6', true),
    -- 板块收盘快照（16:00 收盘批后）
    ('eastmoney_sector_quote', 'sector-quote', 'eastmoney', '5 16 * * 1-5', true),
    -- 港美股指数历史回补：Yahoo 一次性 12 个月，手动触发不排 cron
    ('yahoo_global_index_backfill', 'global-index', 'yahoo', NULL, false)
ON CONFLICT (task_name) DO UPDATE
SET task_type = EXCLUDED.task_type, source = EXCLUDED.source;
