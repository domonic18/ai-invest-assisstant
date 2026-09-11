-- 板块指数日 K（同花顺渠道）：板块详情页真实 OHLC K 线
-- 检测/资金流保持东财体系，经板块名桥接（行业 90/90 同名、概念 ~96% 同名）；
-- THS 代码 881xxx 全局唯一，主键不含 sector_type。幂等可重复执行。

-- ============================================================
-- 1. 板块指数日 K 表
-- ============================================================

CREATE TABLE IF NOT EXISTS quote_kline_sector_daily (
    sector_code VARCHAR(16)  NOT NULL,               -- 同花顺板块代码（881xxx）
    trade_date  DATE         NOT NULL,
    sector_type VARCHAR(16)  NOT NULL CONSTRAINT chk_quote_kline_sector_daily_type
                CHECK (sector_type IN ('industry', 'concept')),
    sector_name VARCHAR(50)  NOT NULL,               -- 桥接键：与东财板块同名
    open        DECIMAL(18, 4),
    high        DECIMAL(18, 4),
    low         DECIMAL(18, 4),
    close       DECIMAL(18, 4) NOT NULL,
    volume      BIGINT,                              -- 成交量（手）
    amount      DECIMAL(20, 2),                      -- 成交额（元）
    source      VARCHAR(20) NOT NULL DEFAULT 'ths',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT pk_quote_kline_sector_daily PRIMARY KEY (sector_code, trade_date)
);

SELECT create_hypertable('quote_kline_sector_daily', 'trade_date', chunk_time_interval => INTERVAL '1 year', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_quote_kline_sector_daily_name_date
    ON quote_kline_sector_daily(sector_name, trade_date DESC);

-- ============================================================
-- 2. ths 渠道接线：sector-kline 数据类型 + 盘后任务
-- ============================================================

UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["sector-kline"]'::jsonb
WHERE source = 'ths'
  AND NOT supported_data_types @> '["sector-kline"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'sector-kline', 1
FROM collector_channel_config
WHERE source = 'ths'
ON CONFLICT (channel_id, data_type) DO NOTHING;

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES
    -- 同花顺板块指数日 K：17:30 收盘批后增量（默认回看 10 日），历史回填手动调大 lookback_days
    ('ths_sector_kline_1730', 'sector-kline', 'ths', '30 17 * * 1-5', true)
ON CONFLICT (task_name) DO NOTHING;
