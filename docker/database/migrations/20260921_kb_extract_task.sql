-- F-KB 批次 D：知识点抽取任务接线（幂等，可全量重放）
-- 与 init-scripts/03-seed.sql 保持同文案（internal 渠道登记 + collector_task 调度行）。

-- internal 渠道补齐 kb-extract 数据类型
UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["kb-extract"]'::jsonb
WHERE source = 'internal'
  AND NOT supported_data_types @> '["kb-extract"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'kb-extract', 1
FROM collector_channel_config
WHERE source = 'internal'
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- 知识点抽取调度：每 10 分钟扫描转写完成素材（状态驱动，无素材即 SKIPPED）
INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES
    ('kb_extract_scan', 'kb-extract', 'internal', '*/10 * * * *', true)
ON CONFLICT (task_name) DO UPDATE
SET task_type = EXCLUDED.task_type, source = EXCLUDED.source;
