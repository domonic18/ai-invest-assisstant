-- 批次 8 PR-1（D21/D23/D24）：盘中自主执行链骨架（shadow 就绪）
--   1) trading_agent.auto_exec_enabled 布尔总闸演进为 intraday_exec_mode 三态
--      （off/shadow/active；DEFAULT shadow = 影子模式先行，paper-trading-plan §11.1）
--   2) agent_run.kind 值域扩展 intraday_tick（驻留进程按日滚动执行会话）
--   3) 新表 paper_trade_exec_observation：逐 tick 判断留痕（L0 判定 + L1 原始
--      概率答案 + 动作/抑制原因），同时是 §11.5 盘中校准观察报告与影子期
--      评测数据集的数据源
-- 幂等：ADD COLUMN IF NOT EXISTS / CREATE TABLE IF NOT EXISTS；重放无副作用。

ALTER TABLE trading_agent ADD COLUMN IF NOT EXISTS intraday_exec_mode VARCHAR(10);

-- backfill 仅在旧列尚存时执行（重放时旧列已 DROP，直接 UPDATE 会报错）
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'trading_agent' AND column_name = 'auto_exec_enabled'
    ) THEN
        UPDATE trading_agent
        SET intraday_exec_mode = CASE WHEN auto_exec_enabled THEN 'shadow' ELSE 'off' END
        WHERE intraday_exec_mode IS NULL;
    END IF;
END $$;

ALTER TABLE trading_agent ALTER COLUMN intraday_exec_mode SET DEFAULT 'shadow';
ALTER TABLE trading_agent ALTER COLUMN intraday_exec_mode SET NOT NULL;
ALTER TABLE trading_agent DROP CONSTRAINT IF EXISTS chk_trading_agent_intraday_exec_mode;
ALTER TABLE trading_agent ADD CONSTRAINT chk_trading_agent_intraday_exec_mode
    CHECK (intraday_exec_mode IN ('off', 'shadow', 'active'));
ALTER TABLE trading_agent DROP COLUMN IF EXISTS auto_exec_enabled;

ALTER TABLE agent_run DROP CONSTRAINT IF EXISTS chk_agent_run_kind;
ALTER TABLE agent_run ADD CONSTRAINT chk_agent_run_kind
    CHECK (kind IN ('plan', 'review', 'intraday_tick'));

CREATE TABLE IF NOT EXISTS paper_trade_exec_observation (
    id                 BIGSERIAL PRIMARY KEY,
    tick_time          TIMESTAMPTZ  NOT NULL,
    trade_date         DATE         NOT NULL,
    agent_key          VARCHAR(32)  NOT NULL REFERENCES trading_agent (agent_key) ON DELETE CASCADE,
    plan_id            BIGINT       REFERENCES agent_trade_plan (id) ON DELETE SET NULL,
    stock_code         VARCHAR(12)  NOT NULL,
    market_snapshot    JSONB,
    l0_verdict         VARCHAR(16)  NOT NULL,
    trigger_reason     VARCHAR(16),
    decision_answers   JSONB,
    action             VARCHAR(16),
    suppression_reason VARCHAR(32),
    is_shadow          BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_paper_trade_exec_observation_agent_date
    ON paper_trade_exec_observation (agent_key, trade_date);
CREATE INDEX IF NOT EXISTS idx_paper_trade_exec_observation_plan
    ON paper_trade_exec_observation (plan_id);
