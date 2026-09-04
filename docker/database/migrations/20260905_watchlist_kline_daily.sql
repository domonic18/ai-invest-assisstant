-- 自选股日 K 自动补采定时任务（幂等可重复执行）
-- watchlist-kline-daily：交易日 16:30 触发（错开 16:00 的 kline 批次），
-- 缺省 symbols = 全部自选股（sina_kline._fetch_watchlist_codes），upsert 幂等

UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["watchlist-kline-daily"]'::jsonb
WHERE source = 'sina'
  AND NOT supported_data_types @> '["watchlist-kline-daily"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'watchlist-kline-daily', 1
FROM collector_channel_config
WHERE source = 'sina'
ON CONFLICT (channel_id, data_type) DO NOTHING;

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES ('watchlist_kline_daily', 'watchlist-kline-daily', 'sina', '30 16 * * 1-5', true)
ON CONFLICT (task_name) DO NOTHING;
