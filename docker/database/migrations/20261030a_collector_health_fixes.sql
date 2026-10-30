-- 采集健康度修复（线上走查 2026-10-30）：
-- 1) collector_task.last_status 的 CHECK 缺 'partial'：部分成功（PARTIAL）任务
--    回写调度状态时触发 IntegrityError，任务进死信且 last_run_at 不再刷新
--    （kline-freshness 每日 PARTIAL 后 last_status 恒失败）。对齐
--    collector_log.status 的同一词表补上 'partial'。
-- 2) sina_stock_list 是「0 2 * * 6」周六任务，却被 trade_day_only=true 预检
--    拦住——周六天然非交易日，自 2026-09-26 起每周静默 SKIPPED，A 股代码
--    宇宙陈旧。列表任务无交易日语义，关闭预检。
-- 3) 港股日 K（eastmoney_hk_kline）16:40 运行时东财尚未发布当日 bar（约
--    18:55 才落地），当日 bar 恒缺、只能靠新浪备源次日补。后移末档到 19:10。
ALTER TABLE collector_task
    DROP CONSTRAINT IF EXISTS collector_task_last_status_check;

ALTER TABLE collector_task
    ADD CONSTRAINT collector_task_last_status_check
    CHECK (last_status IN ('pending', 'running', 'success', 'partial', 'failed', 'skipped'));

UPDATE collector_task
SET trade_day_only = FALSE
WHERE task_name = 'sina_stock_list';

UPDATE collector_task
SET schedule = '10 19 * * 1-5'
WHERE task_name = 'eastmoney_hk_kline';
