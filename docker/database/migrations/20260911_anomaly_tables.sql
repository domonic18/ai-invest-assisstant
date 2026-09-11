-- 异动分析闭环：板块 / 个股异动日表 + 检测定时任务（幂等可重复执行）
-- 方法论与表结构见 docs/arch/08-anomaly-analysis.md §5/§7：
--   sector-anomaly-detect 交易日 16:45（板块收盘快照落库后）
--   stock-anomaly-detect  交易日 17:00（收盘日 K 就绪）
--   均走 internal 渠道 heavy 队列，串行「规则检测 + top-N 归因」

-- ============================================================
-- 1. 板块异动日表
-- ============================================================

CREATE TABLE IF NOT EXISTS market_anomaly_sector (
    id                   BIGSERIAL PRIMARY KEY,
    trade_date           DATE        NOT NULL,
    sector_type          VARCHAR(10) NOT NULL CONSTRAINT chk_market_anomaly_sector_type
                         CHECK (sector_type IN ('industry', 'concept')),
    sector_code          VARCHAR(16) NOT NULL,
    sector_name          VARCHAR(50) NOT NULL,
    change_pct           NUMERIC(8, 4),                -- 当日涨跌幅 %
    amount               NUMERIC(20, 2),               -- 当日成交额（元）
    amount_ratio         NUMERIC(8, 2),                -- 当日额 / 5 日均额
    up_count             INT,
    down_count           INT,
    anomaly_types        JSONB       NOT NULL DEFAULT '[]',  -- 命中维度列表
    strength             INT         NOT NULL,          -- 强度 0-100
    attribution_category VARCHAR(20),                  -- resonance / rotation（归因后回填，可空）
    attribution_summary  TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_market_anomaly_sector UNIQUE (trade_date, sector_type, sector_code)
);

CREATE INDEX IF NOT EXISTS idx_market_anomaly_sector_date
    ON market_anomaly_sector(trade_date DESC);

-- ============================================================
-- 2. 个股异动日表
-- ============================================================

CREATE TABLE IF NOT EXISTS market_anomaly_stock (
    id                   BIGSERIAL PRIMARY KEY,
    trade_date           DATE        NOT NULL,
    stock_code           VARCHAR(10) NOT NULL,
    stock_name           VARCHAR(50) NOT NULL,
    close                NUMERIC(12, 4),
    change_pct           NUMERIC(8, 4),                -- 当日涨跌幅 %
    turnover_rate        NUMERIC(8, 4),                -- 换手率 %
    volume_ratio         NUMERIC(8, 2),                -- 当日量 / 5 日均量
    ma60                 NUMERIC(12, 4),               -- 当日 MA60 值
    is_above_ma60        BOOLEAN     NOT NULL DEFAULT FALSE,
    ma60_breakout        BOOLEAN     NOT NULL DEFAULT FALSE,  -- 当日有效突破 M60
    anomaly_types        JSONB       NOT NULL DEFAULT '[]',
    strength             INT         NOT NULL,
    attribution_category VARCHAR(20),                  -- breakout / acceleration / pullback（可空）
    attribution_summary  TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_market_anomaly_stock UNIQUE (trade_date, stock_code)
);

CREATE INDEX IF NOT EXISTS idx_market_anomaly_stock_date
    ON market_anomaly_stock(trade_date DESC);

-- ============================================================
-- 3. 检测定时任务接线（internal 渠道）
-- ============================================================

UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["sector-anomaly", "stock-anomaly"]'::jsonb
WHERE source = 'internal'
  AND NOT supported_data_types @> '["sector-anomaly", "stock-anomaly"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, d.data_type, 1
FROM collector_channel_config,
     (VALUES ('sector-anomaly'), ('stock-anomaly')) AS d(data_type)
WHERE source = 'internal'
ON CONFLICT (channel_id, data_type) DO NOTHING;

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES
    -- 板块收盘快照（sector-quote 16:05 批次）落库后检测；top-10 归因
    ('sector_anomaly_detect_1645', 'sector-anomaly', 'internal', '45 16 * * 1-5', true),
    -- 收盘日 K 就绪后两段式检测（全市场快照初筛 + 候选新浪日 K 精算）；top-20 归因
    ('stock_anomaly_detect_1700', 'stock-anomaly', 'internal', '0 17 * * 1-5', true)
ON CONFLICT (task_name) DO NOTHING;
