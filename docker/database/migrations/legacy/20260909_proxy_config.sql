-- 代理服务器配置产品化：proxy_config 表 + 采集渠道绑定代理（幂等可重复执行）
-- 渠道经 proxy_config_id 绑定代理（NULL=直连）；删除代理自动解绑（SET NULL）
-- 凭据类配置不入 seed，由管理后台录入（同 llm_config 先例）

CREATE TABLE IF NOT EXISTS proxy_config (
    id                  BIGSERIAL PRIMARY KEY,
    name                VARCHAR(128) NOT NULL,
    protocol            VARCHAR(16)  NOT NULL DEFAULT 'http',
    host                VARCHAR(255) NOT NULL,
    port                INTEGER      NOT NULL,
    username            VARCHAR(255),
    password_encrypted  TEXT,
    is_enabled          BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_proxy_config_name UNIQUE (name),
    CONSTRAINT chk_proxy_config_protocol CHECK (protocol IN ('http', 'socks5')),
    CONSTRAINT chk_proxy_config_port CHECK (port > 0 AND port < 65536)
);

ALTER TABLE collector_channel_config
    ADD COLUMN IF NOT EXISTS proxy_config_id BIGINT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_collector_channel_config_proxy_config'
    ) THEN
        ALTER TABLE collector_channel_config
            ADD CONSTRAINT fk_collector_channel_config_proxy_config
            FOREIGN KEY (proxy_config_id) REFERENCES proxy_config(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_collector_channel_config_proxy_config_id
    ON collector_channel_config(proxy_config_id);
