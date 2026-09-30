-- 盘中计划校准（§11.5，D22）：慢模型早盘/午盘读观察报告对当日计划出修正单。
-- 1) agent_trade_plan.version：校准 adjust 生效即自增，tick 无状态重读自然感知；
-- 2) trading_agent.calibration_mode：off 不参与 / shadow 修正单仅留痕（默认，
--    影子期先行）/ active 修正单生效；
-- 3) agent_trade_plan_amendment：修正单留痕表（applied/shadow/rejected 三态，
--    rejected 记录被确定性硬校验拒绝的原因——校准不是风控旁路）。
-- 幂等：ADD COLUMN IF NOT EXISTS + DO 块兜底重复约束 + CREATE TABLE IF NOT
-- EXISTS；重放无副作用。

ALTER TABLE agent_trade_plan
    ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;

COMMENT ON COLUMN agent_trade_plan.version IS
    '计划版本号：盘中校准 adjust 生效即自增（执行端无状态重读感知变更）';

ALTER TABLE trading_agent
    ADD COLUMN IF NOT EXISTS calibration_mode VARCHAR(16) NOT NULL DEFAULT 'shadow';

DO $$
BEGIN
    ALTER TABLE trading_agent ADD CONSTRAINT chk_trading_agent_calibration_mode
        CHECK (calibration_mode IN ('off', 'shadow', 'active'));
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

COMMENT ON COLUMN trading_agent.calibration_mode IS
    '盘中计划校准三态：off 不参与 / shadow 仅留痕（影子期默认）/ active 生效';

CREATE TABLE IF NOT EXISTS agent_trade_plan_amendment (
    id BIGSERIAL PRIMARY KEY,
    agent_key VARCHAR(32) NOT NULL REFERENCES trading_agent (agent_key) ON DELETE CASCADE,
    plan_date DATE NOT NULL,
    window VARCHAR(8) NOT NULL,
    stock_code VARCHAR(12) NOT NULL,
    plan_id BIGINT REFERENCES agent_trade_plan (id) ON DELETE SET NULL,
    action VARCHAR(16) NOT NULL,
    reason TEXT NOT NULL,
    new_buy_zone_low NUMERIC(12, 4),
    new_buy_zone_high NUMERIC(12, 4),
    new_target_price NUMERIC(12, 4),
    new_stop_loss NUMERIC(12, 4),
    new_position_pct NUMERIC(5, 2),
    status VARCHAR(16) NOT NULL,
    reject_reason TEXT,
    new_plan_id BIGINT,
    model_name VARCHAR(64),
    raw JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_agent_trade_plan_amendment_agent_date_window_code
        UNIQUE (agent_key, plan_date, window, stock_code),
    CONSTRAINT chk_agent_trade_plan_amendment_action
        CHECK (action IN ('maintain', 'adjust', 'cancel', 'add')),
    CONSTRAINT chk_agent_trade_plan_amendment_status
        CHECK (status IN ('applied', 'shadow', 'rejected'))
);

CREATE INDEX IF NOT EXISTS idx_agent_trade_plan_amendment_plan
    ON agent_trade_plan_amendment (plan_id);

COMMENT ON TABLE agent_trade_plan_amendment IS
    '盘中计划校准修正单：慢模型读观察报告对当日计划的修正留痕'
    '（docs/plan/paper-trading-plan.md §11.5）';
COMMENT ON COLUMN agent_trade_plan_amendment.window IS
    '校准窗口：1020（早盘）/ 1320（午盘）';
COMMENT ON COLUMN agent_trade_plan_amendment.status IS
    '生效路径：applied 已落计划 / shadow 影子留痕未生效 / rejected 硬校验拒绝';
COMMENT ON COLUMN agent_trade_plan_amendment.reject_reason IS
    'status=rejected 时的拒绝原因（区间自洽/死单体检/仓位上限）';
COMMENT ON COLUMN agent_trade_plan_amendment.new_plan_id IS
    'action=add 生效时新建计划的 id';
