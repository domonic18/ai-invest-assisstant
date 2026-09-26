-- 交易日历管理：market_trade_calendar 权威日历表 + collector_task.trade_day_only 调度预检开关
-- 方案：docs/plan/trade-calendar-plan.md（D1-D5 已拍板 2026-09-26）
-- 日历表是 A 股交易日的单一真相源：seed=新浪日历自动生成（可被重复刷新），
-- manual=后台人工覆盖（种子刷新不回改人工行）；collector 侧 collector/core/calendar.py
-- 保持 akshare 现状（仅作种子源与 spider 日期缺省兜底），权威判定在 DB。

-- ============================================================
-- 1. 交易日历表（幂等）
-- ============================================================
CREATE TABLE IF NOT EXISTS market_trade_calendar (
    calendar_date DATE         PRIMARY KEY,
    is_trading    BOOLEAN      NOT NULL,
    source        VARCHAR(20)  NOT NULL DEFAULT 'seed' CHECK (source IN ('seed', 'manual')),
    remark        TEXT,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE market_trade_calendar IS
    'A 股交易日历权威真相源：source=seed 新浪日历自动生成 / manual 后台人工覆盖（调休、临时休市）';

-- ============================================================
-- 2. 采集任务调度预检开关（幂等）
-- ============================================================
ALTER TABLE collector_task
    ADD COLUMN IF NOT EXISTS trade_day_only BOOLEAN NOT NULL DEFAULT false;

COMMENT ON COLUMN collector_task.trade_day_only IS
    '交易日预检：true 时 runner 在非交易日/日历未覆盖当日直接 SKIPPED（显式 trade_date 的手动补跑豁免）';

-- 行情类任务开启预检（新闻/全球市场/AI 记分/KB/维护类保持 false）：
UPDATE collector_task
SET trade_day_only = true
WHERE task_name IN (
    'ths_kline_daily', 'watchlist_kline_daily', 'sina_index_kline', 'ths_auction',
    'eastmoney_fund_flow', 'sina_stock_list', 'sina_quote', 'sina_market_breadth',
    'sina_index_spot', 'sina_index_minute', 'tushare_index_auction', 'tushare_index_auction_pm',
    'exchange_market_amount', 'eastmoney_broken_pool', 'eastmoney_sector_fund_flow',
    'eastmoney_limit_up_pool', 'eastmoney_limit_down_pool', 'eastmoney_dragon_list',
    'sina_etf_kline', 'sina_stock_minute', 'sina_a50_kline', 'eastmoney_sector_quote',
    'market_daily_review_1835', 'limit_up_ai_review_1630', 'stock_daily_analysis_1640',
    'sector_anomaly_detect_1745', 'stock_anomaly_detect_1700', 'ths_sector_kline_1730',
    'kline_freshness_evening', 'paper_trade_sync_1600'
);

-- ============================================================
-- 3. 日历种子刷新任务调度（每周一 06:00 北京时间）
-- ============================================================
INSERT INTO collector_task (task_name, task_type, source, schedule, is_active, trade_day_only, remark)
VALUES ('trade_calendar_seed_weekly', 'trade-calendar-seed', 'internal', '0 6 * * 1', true, false,
        '新浪日历刷新 market_trade_calendar（人工覆盖行不回改）')
ON CONFLICT (task_name) DO UPDATE
SET schedule = EXCLUDED.schedule, is_active = EXCLUDED.is_active;

-- ============================================================
-- 4. internal 渠道登记（与 init-scripts/03-seed.sql 同文案；渠道解析按数据类型匹配）
-- ============================================================

UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["trade-calendar-seed"]'::jsonb
WHERE source = 'internal'
  AND NOT supported_data_types @> '["trade-calendar-seed"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'trade-calendar-seed', 1
FROM collector_channel_config
WHERE source = 'internal'
ON CONFLICT (channel_id, data_type) DO NOTHING;
