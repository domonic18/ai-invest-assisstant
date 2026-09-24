-- 大盘复盘推迟到 18:35：新浪指数日 K 当日 bar 源端约 18:00 才可用（深市偶发 18:30，
-- 由 kline_freshness_evening 兜底），16:30 首跑拿不到当日指数行情，残缺复盘还会按
-- input_hash 缓存一整天。实例名随时刻同步更新；日志/监控键为 (task_type, source)
-- 二元组，实例名重命名无下游影响。03-seed.sql 已同步。

UPDATE collector_task
SET task_name = 'market_daily_review_1835',
    schedule = '35 18 * * 1-5'
WHERE task_name = 'market_daily_review_1630';
