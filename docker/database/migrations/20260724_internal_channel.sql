-- 补齐 market-daily-review 的 internal 渠道（幂等可重复执行）
-- 20260722 迁移只插入了 collector_task，未配渠道，resolver 解析为空导致任务每天 skipped

INSERT INTO collector_channel_config (source, name, is_enabled, supported_data_types)
VALUES ('internal', '内部生成', true, '["market-daily-review"]'::jsonb)
ON CONFLICT (source) DO NOTHING;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'market-daily-review', 1
FROM collector_channel_config
WHERE source = 'internal'
ON CONFLICT (channel_id, data_type) DO NOTHING;
