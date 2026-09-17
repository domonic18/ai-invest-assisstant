-- F-SOC 迭代 11：采集与情绪判断双任务接入 collector 体系
-- internal 渠道补 social-sentiment 数据类型；douyin 渠道 + social-video 数据类型；
-- collector_task 登记两条调度（social_video_poll 每小时 / social_sentiment_judge 每 10 分钟）。
-- 幂等：可重复执行。

-- internal 渠道补齐 social-sentiment
UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["social-sentiment"]'::jsonb
WHERE source = 'internal'
  AND NOT supported_data_types @> '["social-sentiment"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'social-sentiment', 1
FROM collector_channel_config
WHERE source = 'internal'
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- douyin 渠道（F-SOC 抖音大V视频采集，Cookie 自持无需 api_key）
INSERT INTO collector_channel_config (source, name, base_url, is_enabled, supported_data_types)
VALUES ('douyin', '抖音', 'https://www.douyin.com', true, '["social-video"]'::jsonb)
ON CONFLICT (source) DO NOTHING;

UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["social-video"]'::jsonb
WHERE source = 'douyin'
  AND NOT supported_data_types @> '["social-video"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'social-video', 1
FROM collector_channel_config
WHERE source = 'douyin'
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- 任务调度登记
INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES
    ('social_video_poll', 'social-video', 'douyin', '0 * * * *', true),
    ('social_sentiment_judge', 'social-sentiment', 'internal', '*/10 * * * *', true)
ON CONFLICT (task_name) DO UPDATE
SET task_type = EXCLUDED.task_type, source = EXCLUDED.source;
