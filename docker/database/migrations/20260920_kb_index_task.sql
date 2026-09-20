-- F-KB 批次 E：知识库索引构建任务登记（internal 渠道 + */5 调度 + 监控白名单）
-- 幂等：重复执行无副作用

-- internal 渠道支持的数据类型清单补 kb-index（渠道已存在时）
UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["kb-index"]'::jsonb
WHERE source = 'internal'
  AND NOT supported_data_types @> '["kb-index"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'kb-index', 1
FROM collector_channel_config
WHERE source = 'internal'
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- 任务实例（每 5 分钟增量扫描三类脏行；无脏行即 SKIPPED）
INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES ('kb_index_scan', 'kb-index', 'internal', '*/5 * * * *', true)
ON CONFLICT (task_name) DO UPDATE
SET task_type = EXCLUDED.task_type, source = EXCLUDED.source;
