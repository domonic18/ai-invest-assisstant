-- paper-trade-position-replay（多周期复盘数据底座，手动触发）internal 渠道接线。
-- 内建任务同样经 resolve_channels_for_task 解析渠道：缺少 supported_data_types
-- 与关联行时返回空候选，run_task 会静默 SKIPPED 而非执行。
-- 幂等：条件追加 + ON CONFLICT DO NOTHING。

UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["paper-trade-position-replay"]'::jsonb
WHERE source = 'internal'
  AND NOT supported_data_types @> '["paper-trade-position-replay"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT c.id, 'paper-trade-position-replay', 1
FROM collector_channel_config c
WHERE c.source = 'internal'
ON CONFLICT (channel_id, data_type) DO NOTHING;
