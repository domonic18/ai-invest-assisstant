-- 为东方财富渠道增加 concept-constituents 任务关联
-- （akshare 已移除同花顺概念成分股接口，改用东方财富数据源）

UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["concept-constituents"]'::jsonb
WHERE source = 'eastmoney'
  AND NOT supported_data_types @> '["concept-constituents"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'concept-constituents', 1
FROM collector_channel_config
WHERE source = 'eastmoney'
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- 移除已失效的同花顺关联
DELETE FROM collector_channel_data_type
WHERE data_type = 'concept-constituents'
  AND channel_id IN (SELECT id FROM collector_channel_config WHERE source = 'ths');

UPDATE collector_channel_config
SET supported_data_types = supported_data_types - 'concept-constituents'
WHERE source = 'ths';
