-- 交易计划死单终态（agent_trade_plan.invalid_reason）。
-- status='invalid' 为首 tick 计划体检（evaluate_plan_sanity）判定的结构性
-- 脱锚死单（现价与买点区间/止损严重背离，当日不再具备执行意义），置终态
-- 后续 tick 不再评判；invalid_reason 记录体检原因供执行动态与计划卡展示。
-- 幂等：ADD COLUMN IF NOT EXISTS；重放无副作用。status 列为 VARCHAR(16)
-- 无 CHECK 约束，'invalid' 值无需 DDL。

ALTER TABLE agent_trade_plan
    ADD COLUMN IF NOT EXISTS invalid_reason TEXT;

COMMENT ON COLUMN agent_trade_plan.invalid_reason IS
    '死单原因（status=invalid 时必填）：首 tick 计划体检判定的结构性脱锚';
