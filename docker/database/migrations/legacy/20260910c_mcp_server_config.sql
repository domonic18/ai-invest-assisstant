-- MCP 服务配置表：后台管理的 MCP server 登记（连接测试 + Phase 2 工具注入）。
-- 幂等：可重复执行。

CREATE TABLE IF NOT EXISTS mcp_server_config (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    transport_type  VARCHAR(10)  NOT NULL DEFAULT 'http', -- stdio | http | sse
    command         VARCHAR(500),                -- stdio：可执行命令
    args            JSONB NOT NULL DEFAULT '[]', -- stdio：命令参数
    url             VARCHAR(500),                -- http/sse：端点
    env             JSONB NOT NULL DEFAULT '{}', -- stdio 环境变量（含密钥）
    headers         JSONB NOT NULL DEFAULT '{}', -- http/sse 认证头
    enabled         BOOLEAN NOT NULL DEFAULT FALSE,
    timeout_seconds INT NOT NULL DEFAULT 30,
    last_status     VARCHAR(20),                 -- ok | failed | untested
    last_error      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_mcp_server_config_name UNIQUE (name),
    CONSTRAINT chk_mcp_server_config_transport_type
        CHECK (transport_type IN ('stdio', 'http', 'sse'))
);
