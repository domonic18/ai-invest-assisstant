-- 集合竞价趋势页：index_auction 表存指数 9:25 集合竞价成交额（单位：元）。
-- 数据源为 tushare stk_auction（纯 9:25 撮合，成分聚合口径）：
-- 9:26~9:29 每分钟重试采集当日数据（9:30 开盘前完成），16:35 盘后兜底。

CREATE TABLE IF NOT EXISTS index_auction (
    id              BIGSERIAL PRIMARY KEY,
    trade_date      DATE         NOT NULL,
    index_code      VARCHAR(10)  NOT NULL,
    auction_amount  DECIMAL(20, 2) NOT NULL,
    source          VARCHAR(50),
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (trade_date, index_code)
);

CREATE INDEX IF NOT EXISTS idx_index_auction_date ON index_auction(trade_date DESC);

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES ('tushare_index_auction', 'index-auction', 'tushare', '26-29 9 * * 1-5', true),
       ('tushare_index_auction_pm', 'index-auction', 'tushare', '35 16 * * 1-5', true)
ON CONFLICT (task_name) DO NOTHING;
