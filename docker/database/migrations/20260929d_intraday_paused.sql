-- 交易 Agent 盘中执行人工暂停开关（trading_agent.intraday_paused）。
-- true 时盘中执行链完全短路：run_tick / run_tail_check 跳过该 Agent
-- （不进 L1 判断模型、不下单、不写观测行、不尾盘强检）；计划/复盘生成
-- 与驻留进程心跳不受影响，恢复后下一拍自动回全流程。
-- 幂等：ADD COLUMN IF NOT EXISTS；重放无副作用（存量行回填 FALSE）。

ALTER TABLE trading_agent
    ADD COLUMN IF NOT EXISTS intraday_paused BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN trading_agent.intraday_paused IS
    '盘中执行人工暂停开关：true 时 tick/尾盘强检完全短路（计划/复盘不受影响）';
