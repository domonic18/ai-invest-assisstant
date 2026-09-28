-- ============================================================
-- 产业链分析版本管理（F-AI-01）
-- 1. 新建 industry_chain_analysis_version 版本表（完整快照 JSONB）
-- 2. 节点/边/公司映射三表加 version_id 与节点指标列，存当前版本
-- ============================================================

CREATE TABLE IF NOT EXISTS industry_chain_analysis_version (
    id               BIGSERIAL PRIMARY KEY,
    industry         VARCHAR(50)  NOT NULL,
    version_number   INT          NOT NULL,
    label            VARCHAR(100),
    status           VARCHAR(20)  NOT NULL DEFAULT 'success'
                     CONSTRAINT chk_industry_chain_analysis_version_status
                     CHECK (status IN ('success', 'failed')),
    snapshot         JSONB        NOT NULL,
    ai_result_id     BIGINT REFERENCES ai_analysis_result(id) ON DELETE SET NULL,
    model            VARCHAR(50),
    node_count       INT,
    company_count    INT,
    error_message    TEXT,
    created_by       VARCHAR(20)  NOT NULL DEFAULT 'manual',
    created_at       TIMESTAMPTZ  DEFAULT NOW(),

    CONSTRAINT uq_industry_chain_analysis_version_industry_version
        UNIQUE (industry, version_number)
);

CREATE INDEX IF NOT EXISTS idx_industry_chain_analysis_version_industry
    ON industry_chain_analysis_version(industry, created_at DESC);

ALTER TABLE industry_chain_node
    ADD COLUMN IF NOT EXISTS version_id BIGINT
        REFERENCES industry_chain_analysis_version(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS avg_gross_margin DECIMAL(8,2),
    ADD COLUMN IF NOT EXISTS revenue_growth   DECIMAL(8,2),
    ADD COLUMN IF NOT EXISTS research_and_development_ratio DECIMAL(8,2),
    ADD COLUMN IF NOT EXISTS bargaining_power DECIMAL(5,2),
    ADD COLUMN IF NOT EXISTS localization_rate DECIMAL(5,2),
    ADD COLUMN IF NOT EXISTS technology_barrier VARCHAR(10),
    ADD COLUMN IF NOT EXISTS bottleneck_indicators TEXT[],
    ADD COLUMN IF NOT EXISTS recent_breakthroughs  TEXT[],
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_industry_chain_node_version
    ON industry_chain_node(version_id);

ALTER TABLE industry_chain_edge
    ADD COLUMN IF NOT EXISTS version_id BIGINT
        REFERENCES industry_chain_analysis_version(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS criticality VARCHAR(10),
    ADD COLUMN IF NOT EXISTS relation_description TEXT;

CREATE INDEX IF NOT EXISTS idx_industry_chain_edge_version
    ON industry_chain_edge(version_id);

ALTER TABLE industry_chain_company_mapping
    ADD COLUMN IF NOT EXISTS version_id BIGINT
        REFERENCES industry_chain_analysis_version(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_industry_chain_company_mapping_version
    ON industry_chain_company_mapping(version_id);
