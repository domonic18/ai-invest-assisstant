-- 行情数据分层落库：交易所官方成交额日表 + market_breadth 炸板家数列。
-- 指数实时快照为实时态数据，走 Redis（sina_index_spot 任务写入），不落 PG。
-- 幂等：IF NOT EXISTS / ADD COLUMN IF NOT EXISTS / ON CONFLICT。

CREATE TABLE IF NOT EXISTS market_amount (
    id              BIGSERIAL PRIMARY KEY,
    trade_date      DATE         NOT NULL,
    amount          DECIMAL(20, 2),
    source          VARCHAR(50),
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (trade_date)
);

ALTER TABLE market_breadth ADD COLUMN IF NOT EXISTS broken_limit_count INT;

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES
    ('sina_index_spot', 'index-spot', 'sina', '* 9-15 * * 1-5', true),
    ('sina_index_minute', 'index-minute', 'sina', '* 9-15 * * 1-5', true),
    ('exchange_market_amount', 'market-amount', 'exchange', '40 15,16,17 * * 1-5', true),
    ('eastmoney_broken_pool', 'broken-pool', 'eastmoney', '40 15 * * 1-5', true)
ON CONFLICT (task_name) DO NOTHING;
