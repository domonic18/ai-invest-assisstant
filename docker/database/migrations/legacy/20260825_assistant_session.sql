-- 2026-08-25: 对话式 AI 助手会话表（阶段 7 Phase 1）
-- id 兼作 Agent Protocol thread_id；消息轨迹由 LangGraph checkpoint 表承载，
-- checkpoint 表由 AsyncPostgresSaver.setup() 自建，不在此迁移。

CREATE TABLE IF NOT EXISTS assistant_session (
    id              UUID PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    title           VARCHAR(128),
    last_message_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_assistant_session_user
    ON assistant_session (user_id, last_message_at DESC);
