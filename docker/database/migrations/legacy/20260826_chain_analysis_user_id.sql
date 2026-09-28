-- ============================================================
-- 产业链分析改为用户级功能 + 字段命名规范化
-- 1. 增加 user_id 字段
-- 2. 重命名以下字段：
--    industry_level_1 -> industry
--    version_no       -> version_number
--    error_msg        -> error_message
--    relation_desc    -> relation_description
--    tech_barrier     -> technology_barrier
--    rd_ratio         -> research_and_development_ratio
-- 3. 版本号唯一约束改为 (user_id, industry, version_number)
-- 4. 增加按用户+行业的查询索引
-- ============================================================

-- 安全重命名辅助函数
CREATE OR REPLACE FUNCTION _rename_column_if_exists(
    p_table TEXT,
    p_old TEXT,
    p_new TEXT
) RETURNS void AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = p_table AND column_name = p_old
    ) THEN
        EXECUTE format('ALTER TABLE %I RENAME COLUMN %I TO %I', p_table, p_old, p_new);
    END IF;
END;
$$ LANGUAGE plpgsql;

-- industry_chain_analysis_version
SELECT _rename_column_if_exists('industry_chain_analysis_version', 'industry_level_1', 'industry');
SELECT _rename_column_if_exists('industry_chain_analysis_version', 'version_no', 'version_number');
SELECT _rename_column_if_exists('industry_chain_analysis_version', 'error_msg', 'error_message');

ALTER TABLE industry_chain_analysis_version
    ADD COLUMN IF NOT EXISTS user_id BIGINT NOT NULL DEFAULT 0;

UPDATE industry_chain_analysis_version
    SET user_id = 0
    WHERE user_id IS NULL;

-- 删除旧唯一约束并重建按用户隔离的约束
ALTER TABLE industry_chain_analysis_version
    DROP CONSTRAINT IF EXISTS uq_industry_chain_analysis_version_industry_version;

ALTER TABLE industry_chain_analysis_version
    DROP CONSTRAINT IF EXISTS uq_industry_chain_analysis_version_user_industry_version;

-- 01-schema.sql 已同步为最终态（含该约束），DROP IF EXISTS 保证全新库上可重复执行
ALTER TABLE industry_chain_analysis_version
    DROP CONSTRAINT IF EXISTS uq_industry_chain_analysis_version_user_industry_version_number;

ALTER TABLE industry_chain_analysis_version
    ADD CONSTRAINT uq_industry_chain_analysis_version_user_industry_version_number
        UNIQUE (user_id, industry, version_number);

CREATE INDEX IF NOT EXISTS idx_industry_chain_analysis_version_user_industry
    ON industry_chain_analysis_version(user_id, industry, created_at DESC);

-- industry_chain_node
SELECT _rename_column_if_exists('industry_chain_node', 'industry_level_1', 'industry');
SELECT _rename_column_if_exists('industry_chain_node', 'rd_ratio', 'research_and_development_ratio');
SELECT _rename_column_if_exists('industry_chain_node', 'tech_barrier', 'technology_barrier');

-- industry_chain_edge
SELECT _rename_column_if_exists('industry_chain_edge', 'relation_desc', 'relation_description');

-- 清理辅助函数
DROP FUNCTION IF EXISTS _rename_column_if_exists(TEXT, TEXT, TEXT);
