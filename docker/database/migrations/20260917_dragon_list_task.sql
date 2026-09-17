-- 龙虎榜定时任务登记（03-seed.sql 同步；此前仅进种子文件未出迁移，
-- 存量环境按本迁移补齐）。龙虎榜数据约 17:30 后稳定发布，盘后批次供涨停归因引用证据。

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES ('eastmoney_dragon_list', 'dragon-list', 'eastmoney', '0 18 * * 1-5', true)
ON CONFLICT (task_name) DO NOTHING;
