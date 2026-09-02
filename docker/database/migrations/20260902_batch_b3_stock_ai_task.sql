-- 个股每日 AI 分析定时任务（幂等可重复执行）
-- stock-daily-analysis：16:40 交易日触发（晚于 market-daily-review 16:30），
-- 遍历开启 AI 复盘分组的自选股逐只生成；个股 K 线/行情未就绪由 Celery 10 分钟退避重试

UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["ai_stock_daily_analysis"]'::jsonb
WHERE source = 'internal'
  AND NOT supported_data_types @> '["ai_stock_daily_analysis"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'ai_stock_daily_analysis', 1
FROM collector_channel_config
WHERE source = 'internal'
ON CONFLICT (channel_id, data_type) DO NOTHING;

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES ('stock_daily_analysis_1640', 'ai_stock_daily_analysis', 'internal', '40 16 * * 1-5', true)
ON CONFLICT (task_name) DO NOTHING;
