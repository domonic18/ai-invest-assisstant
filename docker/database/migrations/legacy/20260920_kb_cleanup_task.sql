-- kb-cleanup 知识库物理清理任务接线（internal 渠道）：
-- 清除软删过窗的源/素材（COS 对象 + 行级联硬删 + 记账归零）、abort 超龄分片会话、
-- 每日一次 deep 孤儿对象扫描。调度 */30 * * * *（北京时间），deep 门控在服务内。

-- 1) internal 渠道 supported_data_types 补齐 kb-cleanup
UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["kb-cleanup"]'::jsonb
WHERE source = 'internal'
  AND NOT supported_data_types @> '["kb-cleanup"]'::jsonb;

-- 2) 渠道-数据类型映射
INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'kb-cleanup', 1
FROM collector_channel_config
WHERE source = 'internal'
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- 3) 任务实例（每 30 分钟；无可清理积压时为良性 SKIPPED）
INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES ('kb_cleanup_0030', 'kb-cleanup', 'internal', '*/30 * * * *', true)
ON CONFLICT (task_name) DO UPDATE
SET task_type = EXCLUDED.task_type, source = EXCLUDED.source;
