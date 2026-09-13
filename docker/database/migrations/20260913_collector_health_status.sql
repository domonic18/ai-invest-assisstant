-- 采集健康监测一期（F-MON）：健康快照表 + 检测定时任务（幂等可重复执行）。
-- 检测由 collector_health_check 定时任务执行（每日 08:30 盘前），判定结果
-- upsert 到 collector_health_status（任务实例 task_type × source 粒度，
-- 常驻 ~50 行）；页面只读快照不再请求路径实时判定。

-- ============================================================
-- 1. 健康快照表
-- ============================================================

CREATE TABLE IF NOT EXISTS collector_health_status (
    id                      BIGSERIAL PRIMARY KEY,
    task_type               VARCHAR(64) NOT NULL,          -- TASK_SPECS 键
    source                  VARCHAR(50) NOT NULL,          -- 渠道标识
    status                  VARCHAR(16) NOT NULL,          -- healthy/degraded/critical/silent/paused/unconfigured
    role                    VARCHAR(8)  NOT NULL,          -- primary/backup/single
    domain                  VARCHAR(16) NOT NULL,          -- 数据域（TASK_TYPE_DOMAIN）
    success_rate_24h        NUMERIC(6, 5),                 -- skipped 剔除口径
    success_rate_7d         NUMERIC(6, 5),
    consecutive_failures    INT         NOT NULL DEFAULT 0,
    last_success_at         TIMESTAMPTZ,
    windows_without_success INT         NOT NULL DEFAULT 0, -- 应成功而未成功的计划窗口数
    last_error_summary      VARCHAR(500),
    last_error_cause        VARCHAR(16),                   -- 错误归因分类
    reasons                 JSONB        NOT NULL DEFAULT '[]'::jsonb, -- 判定依据（why，按序）
    is_high_frequency       BOOLEAN     NOT NULL DEFAULT FALSE, -- 单日场次>=48
    last_records_count      INT,                           -- 最近一次入库量
    last_records_date       DATE,
    state_changed_at        TIMESTAMPTZ NOT NULL,          -- 状态翻转时间
    checked_at              TIMESTAMPTZ NOT NULL,          -- 本次检测时间（同批次同值）

    CONSTRAINT uq_collector_health_status UNIQUE (task_type, source),
    CONSTRAINT chk_collector_health_status_status CHECK (status IN
        ('healthy', 'degraded', 'critical', 'silent', 'paused', 'unconfigured')),
    CONSTRAINT chk_collector_health_status_role CHECK (role IN ('primary', 'backup', 'single'))
);

CREATE INDEX IF NOT EXISTS idx_collector_health_status_status
    ON collector_health_status(status);

-- ============================================================
-- 2. 检测定时任务：internal 渠道登记 health-check + collector_task 行
-- ============================================================

UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["health-check"]'::jsonb
WHERE source = 'internal'
  AND NOT supported_data_types @> '["health-check"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'health-check', 1
FROM collector_channel_config
WHERE source = 'internal'
ON CONFLICT (channel_id, data_type) DO NOTHING;

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES
    -- 采集健康检测：每日 08:30 盘前（对齐盘前巡检场景），判定结果落
    -- collector_health_status；频次可在后台任务配置页调 cron
    ('collector_health_check', 'health-check', 'internal', '30 8 * * *', true)
ON CONFLICT (task_name) DO NOTHING;
