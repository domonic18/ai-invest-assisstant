-- 交易 Agent 经验沉淀底座（docs/plan/paper-trading-plan.md §12.1）。
-- agent_memory = Agent 自有迭代经验（复盘沉淀 + 手动沉淀）：active 条目由每日
-- 计划生成注入 prompt（_MEMORY_TOP_N 截断）；停用 = archived（不物理删除）。
-- 注：方法论基座不走本表——2026-09-26 方案 A 定版为 KB 直读双层注入
--（见 migrations/20260926f_agent_methodology_kb.sql），本表只装经验层。
-- 幂等，可全量重放；与 init-scripts/01-schema.sql 保持同文案。

-- ---------------------------------------------------------------------------
-- 1. 记忆表
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS agent_memory (
    id               BIGSERIAL PRIMARY KEY,
    mem_type         VARCHAR(16)  NOT NULL,      -- discipline 纪律 / method 方法 / lesson 教训
    title            VARCHAR(128) NOT NULL,
    body             TEXT         NOT NULL,
    source           VARCHAR(16)  NOT NULL,      -- auto 复盘自动提取 / manual 人工沉淀
    status           VARCHAR(16)  NOT NULL DEFAULT 'active',   -- active / archived（停用不删）
    source_result_id BIGINT,                     -- ai_analysis_result.id（auto 时必填，溯源）
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agent_memory_source_title UNIQUE (source_result_id, title)
);

CREATE INDEX IF NOT EXISTS idx_agent_memory_status ON agent_memory(status, mem_type);

COMMENT ON TABLE agent_memory IS
    '交易 Agent 自有迭代经验（复盘沉淀 + 手动沉淀，反哺每日计划，docs/plan/paper-trading-plan.md §12.1）';

