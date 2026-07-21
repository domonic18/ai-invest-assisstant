-- 涨停复盘行新增全天分时缩略图，数据来自 kline_minute 个股 1 分钟线。
-- 新浪分钟线须晚于 eastmoney_limit_up_pool（15:35）写入后执行，16:20 首跑、18:20 补跑。

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES ('sina_stock_minute', 'stock-minute', 'sina', '20 16,18 * * 1-5', true)
ON CONFLICT (task_name) DO NOTHING;
