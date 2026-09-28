-- 新浪指数日 K 收盘后发布有延迟，15:30 单跑可能拿不到当日 K 线
-- （实测 2026-07-20 15:30 运行时三大指数最新仍为 07-17）。
-- 增加 18:30 补跑，保证当晚复盘前日 K 齐全。

UPDATE collector_task
SET schedule = '30 15,18 * * 1-5'
WHERE task_name = 'sina_index_kline';
