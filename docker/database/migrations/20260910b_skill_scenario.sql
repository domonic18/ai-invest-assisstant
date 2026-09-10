-- 技能业务场景分类：skill 表新增 scenario 列（技能广场 Tab 用）。
-- builtin 行由启动 sync_builtin_skills 按 registry 回填；custom 行固定 'custom'。
-- 幂等：可重复执行。

ALTER TABLE skill ADD COLUMN IF NOT EXISTS scenario VARCHAR(20);

ALTER TABLE skill DROP CONSTRAINT IF EXISTS chk_skill_scenario;

ALTER TABLE skill ADD CONSTRAINT chk_skill_scenario
    CHECK (scenario IN ('market', 'stock', 'chain', 'report', 'news', 'custom'));

UPDATE skill SET scenario = 'custom' WHERE is_builtin = FALSE AND scenario IS NULL;
