-- 用户组与功能模块权限（迭代：用户组管理）
-- 用户单组（可空 FK）；组权限为功能模块 key 的 JSON 数组；
-- admin 角色代码层不受限，未分组用户默认受限（仅核心浏览功能）。
CREATE TABLE user_group (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(200),
    permissions JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE user_group IS '用户组：按组开通功能模块';

ALTER TABLE "user" ADD COLUMN group_id INTEGER REFERENCES user_group(id);

-- 迁移种子：全功能组，存量非 admin 用户全部指派，保证上线日行为不变；
-- 此后新注册用户默认未分组（受限），由管理员按需建组指派。
INSERT INTO user_group (name, description, permissions)
VALUES (
    '全功能',
    '系统迁移默认组：开通全部功能模块',
    '["kb","assistant","screening","research","financial-reports","paper-trade","skills","news","chain","anomaly","auction","fund-flow"]'::jsonb
);

UPDATE "user"
SET group_id = (SELECT id FROM user_group WHERE name = '全功能')
WHERE role <> 'admin';
