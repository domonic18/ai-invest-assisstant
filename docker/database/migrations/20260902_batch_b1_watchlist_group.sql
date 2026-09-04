-- 批次 B1：自选股分组（幂等可重复执行）
-- user_watchlist_group：用户自选股分组（排序/AI 复盘开关/默认分组不可删）
-- user_watchlist.group_id：单一归属，回填后收紧 NOT NULL

-- ============================================================
-- 分组表
-- ============================================================

CREATE TABLE IF NOT EXISTS user_watchlist_group (
    id                BIGSERIAL PRIMARY KEY,
    user_id           BIGINT       NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    name              VARCHAR(50)  NOT NULL,
    sort_order        INT          NOT NULL DEFAULT 0,
    is_default        BOOLEAN      NOT NULL DEFAULT FALSE,
    ai_review_enabled BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ  DEFAULT NOW(),

    CONSTRAINT uq_user_watchlist_group_user_name UNIQUE (user_id, name)
);

CREATE INDEX IF NOT EXISTS idx_user_watchlist_group_user ON user_watchlist_group(user_id);

-- ============================================================
-- 自选股挂接分组（单一归属）
-- ============================================================

ALTER TABLE user_watchlist
    ADD COLUMN IF NOT EXISTS group_id BIGINT REFERENCES user_watchlist_group(id);

CREATE INDEX IF NOT EXISTS idx_user_watchlist_group_id ON user_watchlist(group_id);

-- 回填：每用户补默认分组（与 service 惰性创建同名，前端展示"默认分组"）
INSERT INTO user_watchlist_group (user_id, name, sort_order, is_default, ai_review_enabled)
SELECT DISTINCT u.id, '默认分组', 0, TRUE, FALSE
FROM "user" u
ON CONFLICT (user_id, name) DO NOTHING;

-- 存量自选股挂入所属用户的默认分组
UPDATE user_watchlist w
SET group_id = g.id
FROM user_watchlist_group g
WHERE g.user_id = w.user_id
  AND g.is_default
  AND w.group_id IS NULL;

ALTER TABLE user_watchlist ALTER COLUMN group_id SET NOT NULL;
