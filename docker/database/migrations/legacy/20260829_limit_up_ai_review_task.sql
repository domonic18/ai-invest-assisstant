-- 涨停板 AI 归因定时任务（幂等可重复执行）
-- limit-up-ai-review：16:30 交易日与大盘复盘同批触发，internal 渠道内部生成
-- 依赖 eastmoney_limit_up_pool 16:00 批次；数据未就绪由 Celery 10 分钟退避重试

UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["limit-up-ai-review"]'::jsonb
WHERE source = 'internal'
  AND NOT supported_data_types @> '["limit-up-ai-review"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'limit-up-ai-review', 1
FROM collector_channel_config
WHERE source = 'internal'
ON CONFLICT (channel_id, data_type) DO NOTHING;

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES ('limit_up_ai_review_1630', 'limit-up-ai-review', 'internal', '30 16 * * 1-5', true)
ON CONFLICT (task_name) DO NOTHING;
