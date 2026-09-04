-- 个股每日 AI 分析定时任务（幂等可重复执行）
-- stock-daily-analysis：16:40 交易日触发（晚于 market-daily-review 16:30），
-- 遍历开启 AI 复盘分组的自选股逐只生成；个股 K 线/行情未就绪由 Celery 10 分钟退避重试
-- 注意：internal 渠道的 supported_data_types 与 collector_channel_data_type.data_type
-- 均按"任务名"（stock-daily-analysis）登记，渠道解析与 beat 派发（collector_task.task_type）
-- 都以任务名为键，与 market-daily-review / limit-up-ai-review 一致。

UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["stock-daily-analysis"]'::jsonb
WHERE source = 'internal'
  AND NOT supported_data_types @> '["stock-daily-analysis"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'stock-daily-analysis', 1
FROM collector_channel_config
WHERE source = 'internal'
ON CONFLICT (channel_id, data_type) DO NOTHING;

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES ('stock_daily_analysis_1640', 'stock-daily-analysis', 'internal', '40 16 * * 1-5', true)
ON CONFLICT (task_name) DO NOTHING;

-- 修复早期误将 data_type（ai_stock_daily_analysis）当任务名登记的残留（新库均为 no-op）
UPDATE collector_channel_config
SET supported_data_types = supported_data_types - 'ai_stock_daily_analysis'
WHERE source = 'internal'
  AND supported_data_types @> '["ai_stock_daily_analysis"]'::jsonb;

DELETE FROM collector_channel_data_type
WHERE data_type = 'ai_stock_daily_analysis'
  AND channel_id IN (SELECT id FROM collector_channel_config WHERE source = 'internal');

UPDATE collector_task
SET task_type = 'stock-daily-analysis'
WHERE task_name = 'stock_daily_analysis_1640'
  AND task_type <> 'stock-daily-analysis';
