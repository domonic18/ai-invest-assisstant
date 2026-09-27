-- news-telegraph-cleanup 电报保留清理任务接线（internal 渠道）：
-- 存储体检（2026-09-27）P3a——每日删除 180 天前财联社电报行（索引
-- publish_time 命中）与 news_ai_score 孤儿标注。调度 10 4 * * *（北京时间），
-- 避开 03:40 采集日志清理窗口。

-- 1) internal 渠道 supported_data_types 补齐 news-telegraph-cleanup
UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["news-telegraph-cleanup"]'::jsonb
WHERE source = 'internal'
  AND NOT supported_data_types @> '["news-telegraph-cleanup"]'::jsonb;

-- 2) 渠道-数据类型映射
INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'news-telegraph-cleanup', 1
FROM collector_channel_config
WHERE source = 'internal'
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- 3) 任务实例（每日 04:10；无可删数据时为良性 SUCCESS 0 删除）
INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES ('news_telegraph_cleanup_daily', 'news-telegraph-cleanup', 'internal', '10 4 * * *', true)
ON CONFLICT (task_name) DO UPDATE
SET task_type = EXCLUDED.task_type, source = EXCLUDED.source;
