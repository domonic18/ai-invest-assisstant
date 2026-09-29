-- 宏观指数页黄金（GC00Y）无历史 K 线修复：全球指标历史回补常态任务
--   1) eastmoney 渠道补齐 global-index-history 数据类型（渠道解析按 TaskSpec.name 匹配）
--   2) 新增调度行 eastmoney_global_index_history：07:30 晨间定盘后 5 日幂等续期；
--      大跨度一次性回填走 CLI `global-index-history --history-days N`
--   3) 实例级用途备注
-- 幂等：条件 UPDATE / ON CONFLICT DO NOTHING / 唯一 task_name UPDATE；重放无副作用。

UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["global-index-history"]'::jsonb
WHERE source = 'eastmoney'
  AND NOT supported_data_types @> '["global-index-history"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'global-index-history', 1
FROM collector_channel_config
WHERE source = 'eastmoney'
ON CONFLICT (channel_id, data_type) DO NOTHING;

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES ('eastmoney_global_index_history', 'global-index-history', 'eastmoney', '30 7 * * 2-6', true)
ON CONFLICT (task_name) DO UPDATE
SET task_type = EXCLUDED.task_type, source = EXCLUDED.source;

UPDATE collector_task SET remark = 'COMEX 黄金/美元指数日 K 历史回补（默认 5 日幂等续期）'
 WHERE task_name = 'eastmoney_global_index_history';
