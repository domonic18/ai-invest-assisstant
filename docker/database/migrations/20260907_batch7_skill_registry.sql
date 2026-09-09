-- 批次7：Skill 注册表（builtin 登记 + custom 定义 JSONB）与用户安装关系。
-- builtin 行不做静态 seed：由应用启动时 sync_builtin_skills 从
-- backend/app/skills/registry.py 幂等同步写入（杜绝 seed 与代码漂移）。
-- 幂等可重复执行。

CREATE TABLE IF NOT EXISTS skill (
    id                BIGSERIAL PRIMARY KEY,
    skill_id          VARCHAR(100) NOT NULL,
    label             VARCHAR(100) NOT NULL,
    kind              VARCHAR(20)  NOT NULL CONSTRAINT chk_skill_kind
                      CHECK (kind IN ('executable', 'prompt_only', 'doc_only', 'custom')),
    description       TEXT,
    is_builtin        BOOLEAN NOT NULL DEFAULT TRUE,
    owner_user_id     BIGINT REFERENCES "user"(id) ON DELETE CASCADE,
    published         BOOLEAN NOT NULL DEFAULT FALSE,
    sort              INT NOT NULL DEFAULT 100,
    custom_definition JSONB,                             -- custom 专用：{skill_md, system_prompt, user_prompt_template?, sections?[]}
    version           INT NOT NULL DEFAULT 1,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_skill_skill_id UNIQUE (skill_id)
);

CREATE INDEX IF NOT EXISTS idx_skill_owner ON skill(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_skill_published_sort ON skill(published, sort);

CREATE TABLE IF NOT EXISTS user_skill (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    skill_id     VARCHAR(100) NOT NULL REFERENCES skill(skill_id) ON DELETE CASCADE,
    enabled      BOOLEAN NOT NULL DEFAULT TRUE,
    sort         INT NOT NULL DEFAULT 100,
    installed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_user_skill_user_skill UNIQUE (user_id, skill_id)
);

CREATE INDEX IF NOT EXISTS idx_user_skill_user ON user_skill(user_id);
CREATE INDEX IF NOT EXISTS idx_user_skill_skill ON user_skill(skill_id);
