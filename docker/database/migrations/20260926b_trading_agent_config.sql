-- 交易 Agent 闭环批次 5：trading_agent_config 单例配置 + assistant_session 会话分流
-- 方案：docs/plan/paper-trading-plan.md §8.5（D19：风控参数与总闸 DB 化，env 覆盖退役）。
-- 单例表恒一行（id=1）：LLM 绑定（空 = 默认 chat 模型）+ 风控阈值（批次 8 消费）+
-- auto_exec_enabled 盘中自主执行总闸；assistant_session.agent_type 区分
-- assistant / trading 会话（/threads 与 /runs 复用同一协议端点，按行分流到对应 agent）。

-- ============================================================
-- 1. trading_agent_config 单例配置表（幂等）
-- ============================================================

CREATE TABLE IF NOT EXISTS trading_agent_config (
    id                     INTEGER       PRIMARY KEY CHECK (id = 1),  -- 恒为 1 的单例行
    llm_config_id          BIGINT,                                    -- 关联 llm_config；空 = 默认 chat 模型
    risk_max_position_pct  NUMERIC(5,2)  NOT NULL DEFAULT 20,         -- 单票市值 ≤ 总资产 %
    risk_max_total_pct     NUMERIC(5,2)  NOT NULL DEFAULT 80,         -- 总持仓市值 ≤ 总资产 %
    risk_max_daily_orders  INTEGER       NOT NULL DEFAULT 10,         -- 单日下单笔数上限
    auto_exec_enabled      BOOLEAN       NOT NULL DEFAULT TRUE,       -- 盘中自主执行总闸（批次 8 轮询入口先检）
    updated_at             TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_trading_agent_config_llm_config
        FOREIGN KEY (llm_config_id) REFERENCES llm_config (id) ON DELETE SET NULL,
    CONSTRAINT chk_trading_agent_config_position_pct
        CHECK (risk_max_position_pct >= 0 AND risk_max_position_pct <= 100),
    CONSTRAINT chk_trading_agent_config_total_pct
        CHECK (risk_max_total_pct >= 0 AND risk_max_total_pct <= 100),
    CONSTRAINT chk_trading_agent_config_daily_orders
        CHECK (risk_max_daily_orders >= 1)
);

COMMENT ON TABLE trading_agent_config IS
    '交易 Agent 全局配置（单例 id=1）：LLM 绑定 + 风控阈值 + 自主执行总闸（docs/plan/paper-trading-plan.md §8.5）';
COMMENT ON COLUMN trading_agent_config.llm_config_id IS
    '对话/选股/复盘共用的 LLM 绑定（llm_config.id）；NULL = 平台默认 chat 模型，改选即时生效';
COMMENT ON COLUMN trading_agent_config.risk_max_position_pct IS
    '风控：单票市值占账户总资产百分比上限（seed 20）';
COMMENT ON COLUMN trading_agent_config.risk_max_total_pct IS
    '风控：总持仓市值占账户总资产百分比上限（seed 80）';
COMMENT ON COLUMN trading_agent_config.risk_max_daily_orders IS
    '风控：单账户单日委托笔数上限（seed 10）';
COMMENT ON COLUMN trading_agent_config.auto_exec_enabled IS
    '盘中自主执行总闸：false 时批次 8 轮询与尾盘强检任务整体 SKIPPED（对话手动交易不受限）';

-- 缺省配置行（管理端「交易 Agent 配置」维护）
INSERT INTO trading_agent_config (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 2. assistant_session 会话分流（幂等；新库 01-schema.sql 已内联该列）
-- ============================================================

ALTER TABLE assistant_session
    ADD COLUMN IF NOT EXISTS agent_type VARCHAR(16) NOT NULL DEFAULT 'assistant';

COMMENT ON COLUMN assistant_session.agent_type IS
    '会话归属的 agent 类型：assistant 主助手 / trading 交易 Agent（线程与运行端点据此分流）';
