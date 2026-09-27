-- 批次 9：复盘经验沉淀 agent_memory——同标题去重 + 刷时间。
-- partial unique 只约束自动沉淀行（manual 允许任意重复标题，由管理员归档）；
-- 冲突路径走 ON CONFLICT DO UPDATE SET updated_at（body 不覆盖，保留人工编辑），
-- 每日计划注入按 updated_at 倒序截断 → 重复出现的教训自动浮头强化。
-- 幂等，可全量重放；与 init-scripts/01-schema.sql 保持同文案。

CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_memory_agent_title_auto
    ON agent_memory (agent_key, title) WHERE source = 'auto';
