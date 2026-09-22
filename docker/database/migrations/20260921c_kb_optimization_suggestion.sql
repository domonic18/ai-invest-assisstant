-- F-KB-07 批次 H2：技能优化建议单（arch/12 §9）
-- 状态机：queued → generating → pending_review → applied / rejected；generating → failed（可重派）
-- 留档语义：skill/source 均为快照字段（不建 FK），技能或知识源删除后建议单仍可追溯。
CREATE TABLE IF NOT EXISTS kb_optimization_suggestion (
    id              SERIAL PRIMARY KEY,
    skill_id        VARCHAR(100) NOT NULL,               -- skill.skill_id（快照键，同技能未处理单禁止新发）
    skill_label     VARCHAR(100) NOT NULL,               -- 技能名快照
    skill_kind      VARCHAR(20)  NOT NULL,               -- builtin / custom 快照
    skill_version   INT          NOT NULL,               -- 生成时技能版本快照
    source_id       BIGINT       NOT NULL,               -- 知识源 id（快照键）
    source_name     VARCHAR(200) NOT NULL,               -- 知识源名快照
    status          VARCHAR(20)  NOT NULL DEFAULT 'queued',
    skill_definition TEXT,                               -- 生成时技能定义全文快照（SKILL.md + prompt.yaml）
    suggestions     JSONB,                               -- 修改点列表 [{targetFile, section, originalText, suggestedText, reason, citations}]
    summary         TEXT,                                -- Agent 总结
    model_name      VARCHAR(100),
    error           TEXT,
    reviewed_by     BIGINT,
    reviewed_at     TIMESTAMPTZ,
    review_note     TEXT,
    apply_result    JSONB,                               -- 审核应用产物（custom：version 快照；builtin：导出文件文本）
    created_by      BIGINT       NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_kb_optimization_status
        CHECK (status IN ('queued', 'generating', 'pending_review', 'applied', 'rejected', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_kb_optimization_skill_status
    ON kb_optimization_suggestion (skill_id, status);
CREATE INDEX IF NOT EXISTS idx_kb_optimization_created
    ON kb_optimization_suggestion (created_at DESC);
