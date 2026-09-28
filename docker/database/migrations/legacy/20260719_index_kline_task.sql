-- 指数日 K 采集调度任务（老库迁移，幂等可重复执行）
-- 新库由 03-seed.sql 直接播种；渠道关联由应用启动时 seed_default_channels 合并

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES ('sina_index_kline', 'index-kline', 'sina', '30 15 * * 1-5', true)
ON CONFLICT (task_name) DO NOTHING;
