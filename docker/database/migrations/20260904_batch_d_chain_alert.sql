-- 批次 D 主线：产业链 AI 提醒表 + 定时刷新任务登记（幂等可重复执行）
-- chain_alert：分析任务产出的具名告警（F-AI-01），同链同类型同日唯一（DO NOTHING 幂等）
-- chain-refresh：每周六 06:00（北京时间）对已有成功版本的产业链重新 AI 分析并落新版本

-- ============================================================
-- chain_alert 表
-- ============================================================

CREATE TABLE IF NOT EXISTS chain_alert (
    id                   BIGSERIAL PRIMARY KEY,
    industry             VARCHAR(50)  NOT NULL,
    alert_type           VARCHAR(20)  NOT NULL,
    severity             INT          NOT NULL,
    title                VARCHAR(200) NOT NULL,
    description          TEXT         NOT NULL,
    affected_segments    TEXT[],
    related_stock_codes  TEXT[],
    signal_date          DATE         NOT NULL,
    version_id           BIGINT REFERENCES industry_chain_analysis_version(id) ON DELETE SET NULL,
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_chain_alert_industry_type_date UNIQUE (industry, alert_type, signal_date),
    CONSTRAINT chk_chain_alert_type CHECK (
        alert_type IN ('财报异动', '评级调整', '技术突破', '格局变化', '政策催化')
    ),
    CONSTRAINT chk_chain_alert_severity CHECK (severity BETWEEN 1 AND 3)
);

CREATE INDEX IF NOT EXISTS idx_chain_alert_industry_signal
    ON chain_alert(industry, signal_date DESC);

-- ============================================================
-- chain-refresh 任务登记（渠道以任务名为键：supported_data_types /
-- collector_channel_data_type.data_type / collector_task.task_type 三处一致）
-- ============================================================

UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["chain-refresh"]'::jsonb
WHERE source = 'internal'
  AND NOT supported_data_types @> '["chain-refresh"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'chain-refresh', 1
FROM collector_channel_config
WHERE source = 'internal'
ON CONFLICT (channel_id, data_type) DO NOTHING;

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES ('chain_refresh_weekly', 'chain-refresh', 'internal', '0 6 * * 6', true)
ON CONFLICT (task_name) DO NOTHING;
