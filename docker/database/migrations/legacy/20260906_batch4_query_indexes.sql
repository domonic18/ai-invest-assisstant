-- 批次 4：查询性能索引补齐（幂等可重复执行）
-- 依据 docs/plan/code-refactoring-plan.md 3.2 节复审结论：
--   ai_analysis_result 的 (skill_id, input_hash) / (skill_id, stock_code) 复合索引
--   缺 status 过滤与 created_at 排序键，缓存读取（load_latest_success /
--   load_success_by_hashes / list_success_trade_dates）每次需回表 + 显式排序；
--   collector_log 的 list_runs_for_task 走 (task_name) 单列 + 排序。
-- 均以更宽复合索引替换旧窄索引（前缀完全包含，旧索引删除以降低写放大）。

-- ============================================================
-- ai_analysis_result
-- ============================================================

-- (skill_id, input_hash) → 追加 status 等值 + created_at 排序：
-- 覆盖 load_latest_success / load_success_by_hashes（DISTINCT ON 取每 hash 最新）
CREATE INDEX IF NOT EXISTS idx_ai_skill_hash_status
    ON ai_analysis_result(skill_id, input_hash, status, created_at DESC);
DROP INDEX IF EXISTS idx_ai_skill_hash;

-- (skill_id, stock_code) → 追加 status 等值 + created_at 范围：
-- 覆盖 list_success_trade_dates（按标的回看 400 天窗口）
CREATE INDEX IF NOT EXISTS idx_ai_skill_stock_status
    ON ai_analysis_result(skill_id, stock_code, status, created_at DESC);
DROP INDEX IF EXISTS idx_ai_skill_code;

-- idx_ai_created_at（created_at DESC 单列）保留：admin 结果列表默认排序与时间筛选

-- ============================================================
-- collector_log
-- ============================================================

-- (task_name) 单列 → (task_name, started_at DESC) 复合：list_runs_for_task 免排序
CREATE INDEX IF NOT EXISTS idx_collector_log_task_started
    ON collector_log(task_name, started_at DESC);
DROP INDEX IF EXISTS idx_collector_log_task_name;

-- task_id 为 ORM 未映射的历史死列，其索引无人使用，随本批清理
DROP INDEX IF EXISTS idx_collector_log_task;

-- 既有 idx_collector_log_status_started_at (status, started_at DESC) 与
-- idx_collector_log_started (started_at DESC) 已覆盖状态/时间查询，不动
