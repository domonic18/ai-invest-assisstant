-- ============================================================
-- K 线 AI 画线多租户隔离（迭代 8/9 交付后多租户口径修正）
-- ai_kline_drawing 从「全局共享工作区」改为 per-user 私有：
-- 1) 加 user_id 归属列（存量行回填给首个 admin——单主人时期的产出归属）
-- 2) 唯一约束 (target_type, target_code, period) → (user_id, target_type, target_code, period)
-- 幂等可重复执行；01-schema.sql 已同步
-- ============================================================

ALTER TABLE ai_kline_drawing ADD COLUMN IF NOT EXISTS user_id BIGINT REFERENCES "user"(id) ON DELETE CASCADE;

UPDATE ai_kline_drawing
SET user_id = (SELECT id FROM "user" WHERE role = 'admin' ORDER BY id LIMIT 1)
WHERE user_id IS NULL;
UPDATE ai_kline_drawing
SET user_id = (SELECT MIN(id) FROM "user")
WHERE user_id IS NULL AND (SELECT COUNT(*) FROM "user") > 0;

ALTER TABLE ai_kline_drawing ALTER COLUMN user_id SET NOT NULL;

ALTER TABLE ai_kline_drawing DROP CONSTRAINT IF EXISTS uq_ai_kline_drawing;
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_ai_kline_drawing'
    ) THEN
        ALTER TABLE ai_kline_drawing
            ADD CONSTRAINT uq_ai_kline_drawing UNIQUE (user_id, target_type, target_code, period);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_ai_kline_drawing_scope
    ON ai_kline_drawing(user_id, target_type, target_code, period);
