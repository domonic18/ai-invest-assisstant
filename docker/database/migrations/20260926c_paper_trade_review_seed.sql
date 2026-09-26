-- 交易 Agent 闭环批次 6：模拟盘 AI 分层复盘定时任务（docs/plan/paper-trading-plan.md §9）。
-- 16:10 串行在 16:00 盘后同步之后（北京时区，heavy 队列）；周五 / 月末最后一个交易日
-- 的周/月度加发在任务内用交易日历判定（cron 表达不了「最后交易日」）。
-- 既有部署补 seed 行；与 init-scripts/03-seed.sql 保持同文案（幂等，可全量重放）。

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES ('paper_trade_review_1610', 'paper-trade-review', 'internal', '10 16 * * 1-5', true)
ON CONFLICT (task_name) DO UPDATE
SET task_type = EXCLUDED.task_type, source = EXCLUDED.source, schedule = EXCLUDED.schedule;

-- 交易日才执行（非交易日 SKIPPED，与其他盘后链任务同口径）
UPDATE collector_task SET trade_day_only = true WHERE task_name = 'paper_trade_review_1610';

-- internal 渠道补登记 paper-trade-review（缺行时 resolver 报「没有启用任何可用的采集渠道」）
UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["paper-trade-review"]'::jsonb
WHERE source = 'internal'
  AND NOT supported_data_types @> '["paper-trade-review"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'paper-trade-review', 1
FROM collector_channel_config
WHERE source = 'internal'
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- 防御性补齐 paper-trade-sync 渠道登记（批次 4 仅迁移补过存量环境，init-scripts 缺行）
UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["paper-trade-sync"]'::jsonb
WHERE source = 'internal'
  AND NOT supported_data_types @> '["paper-trade-sync"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'paper-trade-sync', 1
FROM collector_channel_config
WHERE source = 'internal'
ON CONFLICT (channel_id, data_type) DO NOTHING;
