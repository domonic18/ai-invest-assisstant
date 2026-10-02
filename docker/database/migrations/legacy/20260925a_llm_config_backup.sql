-- LLM 主备切换：llm_config 增加备用配置引用（2026-09-25）
-- 主配置上游额度耗尽（限流 429/402）进入冷却期时，解析层自动切换到
-- backup_config_id 指向的备用条目。无 FK：引用有效性（存在/启用/
-- 同 purpose/非自身）由服务层校验，删除条目时由服务层清理反向引用。

ALTER TABLE llm_config ADD COLUMN IF NOT EXISTS backup_config_id INTEGER;

COMMENT ON COLUMN llm_config.backup_config_id IS
    '备用配置 id：本配置额度耗尽冷却期内解析层自动切换的目标（单级，不链式）';
