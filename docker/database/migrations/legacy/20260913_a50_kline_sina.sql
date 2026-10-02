-- a50-kline 主渠道切换：eastmoney push2his kline 路径被 WAF 路径级封死
-- （TLS 指纹无关，curl_cffi Chrome 指纹同样被拒），改由 sina 全球期货
-- CHA50CFD 承担（spider sina_a50_kline）。eastmoney 采集器保留为兜底渠道，
-- 但停用其定时行，避免每日注定失败的采集告警噪音。

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES ('sina_a50_kline', 'a50-kline', 'sina', '40 17,21 * * 1-5', true)
ON CONFLICT (task_name) DO NOTHING;

UPDATE collector_task
SET is_active = false, updated_at = NOW()
WHERE task_name = 'eastmoney_a50_kline'
  AND is_active;

-- 防御性补齐 sina 渠道的 a50-kline 关联（应用启动 seed_default_channels 也会补，
-- 迁移先行保证部署窗口内 beat 派发即可解析到主渠道；priority=1 < eastmoney 兜底）
INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'a50-kline', 1
FROM collector_channel_config
WHERE source = 'sina'
ON CONFLICT (channel_id, data_type) DO NOTHING;
