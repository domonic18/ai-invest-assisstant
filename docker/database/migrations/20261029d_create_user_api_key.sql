-- 多租户 MCP 凭证（docs/requirement/10-mcp-multi-tenant-requirement.md）。
-- 库内只存 HMAC-SHA256(pepper, token)，明文仅在签发响应中出现一次；
-- key_prefix 为人类可读前缀（列表展示/排障），不参与校验。
CREATE TABLE IF NOT EXISTS user_api_key (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT       NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    name         VARCHAR(100) NOT NULL,
    key_prefix   VARCHAR(16)  NOT NULL,
    key_hash     VARCHAR(64)  NOT NULL UNIQUE,
    scopes       TEXT[]       NOT NULL DEFAULT '{}',
    expires_at   TIMESTAMPTZ,
    revoked_at   TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

COMMENT ON TABLE user_api_key IS '用户 API Key：外部 MCP 客户端访问凭证（多租户）';
COMMENT ON COLUMN user_api_key.key_hash IS 'HMAC-SHA256(pepper, 完整 token)，校验唯一依据';
COMMENT ON COLUMN user_api_key.scopes IS '权限范围清单（market:read/trading:read/kb:read 等）';

CREATE INDEX IF NOT EXISTS idx_user_api_key_user_id ON user_api_key (user_id);
