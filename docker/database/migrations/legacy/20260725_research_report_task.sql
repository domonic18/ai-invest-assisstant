-- 注册 eastmoney research-report 定时任务（幂等可重复执行）
-- 研报列表来自东财 reportapi，PDF 落 MinIO；每日 8 点/18 点采集

-- 防御性补齐 eastmoney 渠道的 research-report 数据类型（渠道已存在时）
UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["research-report"]'::jsonb
WHERE source = 'eastmoney'
  AND NOT supported_data_types @> '["research-report"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'research-report', 1
FROM collector_channel_config
WHERE source = 'eastmoney'
ON CONFLICT (channel_id, data_type) DO NOTHING;

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES ('eastmoney_research_report', 'research-report', 'eastmoney', '0 8,18 * * *', true)
ON CONFLICT (task_name) DO NOTHING;
