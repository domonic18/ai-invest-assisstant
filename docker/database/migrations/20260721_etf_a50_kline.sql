-- 新增沪深300ETF（sina）与富时A50期指（eastmoney）日 K 采集任务。
-- A50 期指日盘 16:30 收盘，17:40 取当日日 K，21:40 夜盘修正。

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES
    ('sina_etf_kline', 'etf-kline', 'sina', '5 16 * * 1-5', true),
    ('eastmoney_a50_kline', 'a50-kline', 'eastmoney', '40 17,21 * * 1-5', true)
ON CONFLICT (task_name) DO NOTHING;
