-- F-KB 批次 B：知识库课程转写任务接线（幂等，可全量重放）
-- 与 init-scripts/03-seed.sql 保持同文案（internal 渠道登记 + collector_task 调度行）。

-- internal 渠道补齐 kb-transcribe 数据类型
UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["kb-transcribe"]'::jsonb
WHERE source = 'internal'
  AND NOT supported_data_types @> '["kb-transcribe"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'kb-transcribe', 1
FROM collector_channel_config
WHERE source = 'internal'
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- 课程转写调度：每 5 分钟扫描 queued 素材（状态驱动，无素材即 SKIPPED）
INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES
    ('kb_transcribe_scan', 'kb-transcribe', 'internal', '*/5 * * * *', true)
ON CONFLICT (task_name) DO UPDATE
SET task_type = EXCLUDED.task_type, source = EXCLUDED.source;
