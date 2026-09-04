-- 市场涨跌统计表：采集器每 5 分钟（交易时段）写入全市场快照统计，
-- stats 接口只读本表，不再在请求路径抓取新浪。
-- 幂等：IF NOT EXISTS / ON CONFLICT。

CREATE TABLE IF NOT EXISTS market_breadth (
    id              BIGSERIAL PRIMARY KEY,
    trade_date      DATE         NOT NULL,
    up_count        INT,
    down_count      INT,
    flat_count      INT,
    limit_up_count  INT,
    limit_down_count INT,
    snapshot_time       VARCHAR(20),
    source          VARCHAR(50),
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (trade_date)
);

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES ('sina_market_breadth', 'market-breadth', 'sina', '2-57/5 9-15 * * 1-5', true)
ON CONFLICT (task_name) DO NOTHING;
