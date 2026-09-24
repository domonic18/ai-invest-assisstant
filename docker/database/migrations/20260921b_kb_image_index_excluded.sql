-- ============================================================
-- 图片资产治理：人工排除不进检索索引（重新描述/排除工作台配套）
-- 幂等，可全量重放。与 init-scripts/01-schema.sql 同步。
-- ============================================================

ALTER TABLE kb_image_asset ADD COLUMN IF NOT EXISTS index_excluded BOOLEAN NOT NULL DEFAULT FALSE;
