-- 20260928a_agent_run_observability.sql
-- Agent 会话管理（D35）：交易 Agent 自动化任务执行轨迹落库——
-- agent_run 会话头（plan/review 各一次生成一条，含触发方式/状态/摘要）+
-- agent_run_step 执行步骤明细（输入组装/LLM 调用/校验/落库，payload 全文截断存储）。
-- 观测数据与业务事务解耦：recorder 独立 session 写入，agent 删除时级联清理历史。

CREATE TABLE IF NOT EXISTS agent_run (
    id               BIGSERIAL PRIMARY KEY,
    agent_key        VARCHAR(32)  NOT NULL REFERENCES trading_agent (agent_key) ON DELETE CASCADE,  -- 归属 Agent
    kind             VARCHAR(16)  NOT NULL,      -- plan 每日计划 / review 分层复盘
    period           VARCHAR(16),                -- day / week / month（review 必填；plan 存 cadence 映射）
    trigger_type     VARCHAR(16)  NOT NULL DEFAULT 'scheduled',  -- scheduled 定时 / manual 手动
    trade_date       DATE,                       -- 基准交易日
    status           VARCHAR(16)  NOT NULL,      -- running / success / failed / skipped（缓存命中等）
    started_at       TIMESTAMPTZ NOT NULL,
    finished_at      TIMESTAMPTZ,
    duration_ms      INT,
    error_msg        TEXT,
    summary          JSONB,                      -- 结果摘要：cache_hit / kb_used / selections / plans / dropped_codes 等
    collector_log_id BIGINT,                     -- collector_log.id（定时链路溯源）
    CONSTRAINT chk_agent_run_kind CHECK (kind IN ('plan', 'review')),
    CONSTRAINT chk_agent_run_trigger CHECK (trigger_type IN ('scheduled', 'manual')),
    CONSTRAINT chk_agent_run_status CHECK (status IN ('running', 'success', 'failed', 'skipped'))
);

CREATE INDEX IF NOT EXISTS idx_agent_run_key_time
    ON agent_run(agent_key, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_run_status_running
    ON agent_run(status) WHERE status = 'running';

COMMENT ON TABLE agent_run IS
    '交易 Agent 自动化任务执行会话（会话管理真相源，docs/plan/agent-hub-plan.md D35）';

CREATE TABLE IF NOT EXISTS agent_run_step (
    id          BIGSERIAL PRIMARY KEY,
    run_id      BIGINT      NOT NULL REFERENCES agent_run (id) ON DELETE CASCADE,
    seq         INT         NOT NULL,          -- 步骤序号（从 1 递增）
    step_key    VARCHAR(64) NOT NULL,          -- 步骤标识：precheck / input.market_review / llm / validate / persist 等
    title       VARCHAR(128),                  -- 展示标题
    status      VARCHAR(16) NOT NULL,          -- success / failed
    started_at  TIMESTAMPTZ,
    duration_ms INT,
    payload     JSONB,                         -- 步骤完整输入输出（代码层 8KB/段截断）
    CONSTRAINT uq_agent_run_step_seq UNIQUE (run_id, seq)
);

COMMENT ON TABLE agent_run_step IS
    '交易 Agent 会话执行步骤明细（工具调用/KB 检索/LLM 全文，D35）';
