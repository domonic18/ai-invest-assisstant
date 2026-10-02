-- ============================================================
-- 任务日志提示分层：SKIPPED 说明与错误分离（幂等，可全量重放）
-- collector_log.message 承载跳过原因等非错误说明；error_msg 回归
-- 纯错误语义（failed/partial）。历史 skipped 行的 error_msg 平移。
-- 与 init-scripts/01-schema.sql 同步。
-- ============================================================

ALTER TABLE collector_log ADD COLUMN IF NOT EXISTS message TEXT;

UPDATE collector_log
SET message = error_msg, error_msg = NULL
WHERE status = 'skipped'
  AND error_msg IS NOT NULL
  AND error_msg <> '';
