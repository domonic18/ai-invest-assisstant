-- 修复 schema drift：users 表缺 settings 列导致登录 500
-- init-scripts/01-schema.sql 已含该列，但既有库未同步

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS settings JSONB DEFAULT '{}'::jsonb;
