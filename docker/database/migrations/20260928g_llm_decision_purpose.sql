-- 批次 8.0（D23 判断模型接入层）：llm_config 枚举扩值
--   purpose += 'decision'（结构化判断用途，判断模型配置行）
--   protocol += 'systemone'（System One wire 协议，POST {base}/v1/systemone）
-- 幂等：DROP IF EXISTS + ADD CONSTRAINT 成对；重放无副作用。

ALTER TABLE llm_config DROP CONSTRAINT IF EXISTS chk_llm_config_purpose;
ALTER TABLE llm_config ADD CONSTRAINT chk_llm_config_purpose
    CHECK (purpose IN ('chat', 'embedding', 'vision', 'decision'));

ALTER TABLE llm_config DROP CONSTRAINT IF EXISTS chk_llm_config_protocol;
ALTER TABLE llm_config ADD CONSTRAINT chk_llm_config_protocol
    CHECK (protocol IN ('openai', 'anthropic', 'systemone'));
