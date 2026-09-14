-- ============================================================
-- 迭代 10 · 账号准入与 AI 用量治理（F-ACCT）
-- 1) user 表审批状态列（存量行 DEFAULT 'approved' 即达标）
-- 2) 一次性配额真相源 user_ai_quota（存量 approved 用户回填默认 10 万）
-- 3) 逐次 token 计量明细 user_token_usage
-- 4) 用户自备 Key（BYOK）配置 user_llm_config
-- 5) 管理端审计 admin_audit_log + 运行时全局设置 system_setting
-- 幂等可重复执行；01-schema.sql 已同步（新部署走 init-scripts）
-- ============================================================

ALTER TABLE "user" ADD COLUMN IF NOT EXISTS status VARCHAR(16) NOT NULL DEFAULT 'approved';
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS application_note TEXT;
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS reject_reason TEXT;
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS reviewed_by BIGINT REFERENCES "user"(id);
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_user_status'
    ) THEN
        ALTER TABLE "user"
            ADD CONSTRAINT chk_user_status CHECK (status IN ('pending', 'approved', 'rejected'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_user_status_pending ON "user"(status) WHERE status = 'pending';

CREATE TABLE IF NOT EXISTS user_ai_quota (
    user_id     BIGINT PRIMARY KEY REFERENCES "user"(id) ON DELETE CASCADE,
    total_tokens BIGINT,                                -- NULL = 不设上限（豁免）
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by  BIGINT REFERENCES "user"(id)
);

CREATE TABLE IF NOT EXISTS user_token_usage (
    id                BIGSERIAL PRIMARY KEY,
    user_id           BIGINT REFERENCES "user"(id) ON DELETE SET NULL,  -- 系统维度为 NULL
    feature           VARCHAR(20) NOT NULL,              -- assistant / page / api_key / system
    model_name        VARCHAR(100) NOT NULL,
    provider          VARCHAR(50)  NOT NULL,             -- 渠道 provider 或 'byok'
    outlet            VARCHAR(10)  NOT NULL,             -- system / byok
    prompt_tokens     INT NOT NULL,
    completion_tokens INT NOT NULL,
    total_tokens      INT NOT NULL,
    estimated         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_usage_feature CHECK (feature IN ('assistant', 'page', 'api_key', 'system')),
    CONSTRAINT chk_usage_outlet CHECK (outlet IN ('system', 'byok'))
);

CREATE INDEX IF NOT EXISTS idx_usage_user_time ON user_token_usage(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_time ON user_token_usage(created_at);
CREATE INDEX IF NOT EXISTS idx_usage_feature_time ON user_token_usage(feature, created_at);

CREATE TABLE IF NOT EXISTS user_llm_config (
    id                BIGSERIAL PRIMARY KEY,
    user_id           BIGINT NOT NULL UNIQUE REFERENCES "user"(id) ON DELETE CASCADE,
    protocol          VARCHAR(20) NOT NULL,
    base_url          VARCHAR(255) NOT NULL,
    model_name        VARCHAR(100) NOT NULL,
    api_key_encrypted TEXT NOT NULL,                     -- Fernet 认证加密（app/utils/crypto.py）
    api_key_masked    VARCHAR(32)  NOT NULL,             -- 冗余脱敏串，读路径免解密
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_user_llm_protocol CHECK (protocol IN ('openai', 'anthropic'))
);

CREATE TABLE IF NOT EXISTS admin_audit_log (
    id             BIGSERIAL PRIMARY KEY,
    actor_id       BIGINT NOT NULL REFERENCES "user"(id),
    action         VARCHAR(50) NOT NULL,                 -- register.approve / register.reject / quota.adjust / account_setting.update
    target_user_id BIGINT REFERENCES "user"(id) ON DELETE SET NULL,
    detail         JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip             VARCHAR(45),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_actor_time ON admin_audit_log(actor_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_action_time ON admin_audit_log(action, created_at DESC);

CREATE TABLE IF NOT EXISTS system_setting (
    key        VARCHAR(50) PRIMARY KEY,                  -- account.default_quota_tokens / account.pending_expire_days / quota.admin_exempt
    value      JSONB NOT NULL,
    updated_by BIGINT REFERENCES "user"(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 存量 approved 用户一次性回填默认配额（10 万 tokens，与 system_setting 缺省同源）
INSERT INTO user_ai_quota (user_id, total_tokens)
SELECT id, 100000 FROM "user" WHERE status = 'approved'
ON CONFLICT (user_id) DO NOTHING;

-- 全局设置缺省行（管理端可改）
INSERT INTO system_setting (key, value) VALUES
    ('account.default_quota_tokens', '100000'),
    ('account.pending_expire_days', '30'),
    ('quota.admin_exempt', 'true')
ON CONFLICT (key) DO NOTHING;
