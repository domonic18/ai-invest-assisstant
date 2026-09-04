-- 财联社投资日历定时任务（幂等可重复执行）
-- cls-investkalendar：每日 07:15（北京时间）拉取 investkalendar 前瞻窗口
-- （端点固定返回今日起约 3 周，tradeDate 不改变窗口），source_hash 幂等
-- DO NOTHING。日历含周末会议类事件，调度不设星期过滤。
-- 渠道登记以任务名为键（批次 B 教训）：cls 渠道 supported_data_types、
-- collector_channel_data_type.data_type、collector_task.task_type 三处一致。

UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["cls-investkalendar"]'::jsonb
WHERE source = 'cls'
  AND NOT supported_data_types @> '["cls-investkalendar"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'cls-investkalendar', 1
FROM collector_channel_config
WHERE source = 'cls'
ON CONFLICT (channel_id, data_type) DO NOTHING;

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES ('cls_investkalendar_daily', 'cls-investkalendar', 'cls', '15 7 * * *', true)
ON CONFLICT (task_name) DO NOTHING;
