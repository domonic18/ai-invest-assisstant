-- collector_task.last_status 放宽含 'skipped'。
-- SKIPPED 是采集器良性终态（非交易日/无可清理积压），CollectorStatus 枚举含该值；
-- 旧约束下每次 skip 状态写回必违反约束，被外层兜底改记为 failed 且 last_error 记录
-- IntegrityError 文本（2026-09-19 kb_cleanup_0030 首轮踩中暴露）。
ALTER TABLE collector_task DROP CONSTRAINT IF EXISTS collector_task_last_status_check;
ALTER TABLE collector_task ADD CONSTRAINT collector_task_last_status_check
    CHECK (last_status IN ('pending', 'running', 'success', 'failed', 'skipped'));
