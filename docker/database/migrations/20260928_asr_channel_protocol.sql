-- ASR 渠道配置支持多厂商：新增 protocol 字段（wire 协议，决定端点与请求/错误形态）。
-- 存量行回填 'minimax' 保持现有行为零感知；CHECK 约束防脏协议入库。

ALTER TABLE asr_channel_config
    ADD COLUMN IF NOT EXISTS protocol TEXT NOT NULL DEFAULT 'minimax';

ALTER TABLE asr_channel_config
    DROP CONSTRAINT IF EXISTS chk_asr_channel_config_protocol;

ALTER TABLE asr_channel_config
    ADD CONSTRAINT chk_asr_channel_config_protocol
    CHECK (protocol IN ('minimax', 'openai'));
