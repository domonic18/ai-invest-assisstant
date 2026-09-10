-- LLM 配置增加协议类型字段：openai 兼容 / anthropic（幂等可重复执行）
-- build_langchain_model 与连通性测试探针按 protocol 分支，provider 退化为渠道展示标识。

ALTER TABLE llm_config ADD COLUMN IF NOT EXISTS protocol VARCHAR(20) NOT NULL DEFAULT 'openai';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_llm_config_protocol'
    ) THEN
        ALTER TABLE llm_config ADD CONSTRAINT chk_llm_config_protocol
            CHECK (protocol IN ('openai', 'anthropic'));
    END IF;
END $$;

-- 存量 anthropic 协议渠道（kimi 等）回填
UPDATE llm_config SET protocol = 'anthropic' WHERE provider = 'anthropic';
