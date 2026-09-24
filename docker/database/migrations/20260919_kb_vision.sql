-- ============================================================
-- F-KB 批次 I：课程视频关键帧通道数据底座（幂等，可全量重放）
-- kb_image_asset 泛化为「书嵌图 + 课程关键帧」统一落表；
-- kb_media.vision_at 为选帧幂等键。与 init-scripts/01-schema.sql 同步。
-- ============================================================

-- 关键帧按时间码定位（page_no 留给书嵌图，课程行为空）
ALTER TABLE kb_image_asset ALTER COLUMN page_no DROP NOT NULL;
ALTER TABLE kb_image_asset ADD COLUMN IF NOT EXISTS start_ms BIGINT;
ALTER TABLE kb_image_asset ADD COLUMN IF NOT EXISTS end_ms BIGINT;

-- 视觉描述失败退避（≥3 终态 failed，防坏行无限重试烧钱）
ALTER TABLE kb_image_asset ADD COLUMN IF NOT EXISTS describe_attempts INT NOT NULL DEFAULT 0;

-- 课程视频关键帧选帧完成时刻（视觉通道幂等键，重跑不重抽）
ALTER TABLE kb_media ADD COLUMN IF NOT EXISTS vision_at TIMESTAMPTZ;

-- ------------------------------------------------------------
-- kb-vision 任务接线（与 init-scripts/03-seed.sql 同文案）
-- ------------------------------------------------------------

UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["kb-vision"]'::jsonb
WHERE source = 'internal'
  AND NOT supported_data_types @> '["kb-vision"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'kb-vision', 1
FROM collector_channel_config
WHERE source = 'internal'
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- 视频关键帧调度：每 10 分钟两阶段扫描（选帧零 LLM + 描述按张计费，无素材即 SKIPPED）
INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES
    ('kb_vision_scan', 'kb-vision', 'internal', '*/10 * * * *', true)
ON CONFLICT (task_name) DO UPDATE
SET task_type = EXCLUDED.task_type, source = EXCLUDED.source;
