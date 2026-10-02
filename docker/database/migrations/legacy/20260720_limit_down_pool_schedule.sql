-- 跌停池收盘调度：stats 跌停数改以东财官方池（不含 ST）为准。
-- 调度定在 16:00：须晚于 sina_market_breadth 最后一次写入（15:57），
-- 否则官方池家数会被新浪快照估算覆盖。

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES
    ('eastmoney_limit_down_pool', 'limit-down-pool', 'eastmoney', '0 16 * * 1-5', true)
ON CONFLICT (task_name) DO NOTHING;
