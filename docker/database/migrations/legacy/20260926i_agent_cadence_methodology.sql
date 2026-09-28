-- 20260926i_agent_cadence_methodology.sql
-- Agent Hub 验收修复（D28）：
-- 1) trading_agent 加 plan_cadence / review_cadence（计划/复盘生成频率，daily/weekly/monthly）
-- 2) long-line 种子频率 = weekly（中长线周度计划与复盘；short-line/m60 默认 daily）
-- 3) methodology_source_id 回填温程趋势理论 KB 源（id=1 存在时；init 纯新库无 KB 数据不回填，经配置面设置）

ALTER TABLE trading_agent
    ADD COLUMN IF NOT EXISTS plan_cadence VARCHAR(16) NOT NULL DEFAULT 'daily';
ALTER TABLE trading_agent
    ADD COLUMN IF NOT EXISTS review_cadence VARCHAR(16) NOT NULL DEFAULT 'daily';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_trading_agent_plan_cadence'
    ) THEN
        ALTER TABLE trading_agent ADD CONSTRAINT chk_trading_agent_plan_cadence
            CHECK (plan_cadence IN ('daily', 'weekly', 'monthly'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_trading_agent_review_cadence'
    ) THEN
        ALTER TABLE trading_agent ADD CONSTRAINT chk_trading_agent_review_cadence
            CHECK (review_cadence IN ('daily', 'weekly', 'monthly'));
    END IF;
END $$;

UPDATE trading_agent
SET plan_cadence = 'weekly', review_cadence = 'weekly'
WHERE agent_key = 'long-line'
  AND (plan_cadence <> 'weekly' OR review_cadence <> 'weekly');

UPDATE trading_agent
SET methodology_source_id = 1
WHERE methodology_source_id IS NULL
  AND EXISTS (SELECT 1 FROM kb_source WHERE id = 1);
