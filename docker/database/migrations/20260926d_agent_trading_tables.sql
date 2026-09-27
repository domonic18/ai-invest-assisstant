-- 交易 Agent 闭环批次 7：每日选股与交易计划数据底座（docs/plan/paper-trading-plan.md §10.1）。
-- agent_stock_selection = 选股依据真相源（复盘归因输入 + 人工移出干预记录）；
-- agent_trade_plan = 盘中条件触发的真相源（批次 8 执行服务读表）。
-- user_watchlist_group 加 owner_type 并放开 user_id：agent 分组为平台级单例
-- （user_id=NULL，不命中既有 user_id 过滤、不受用户删除级联）。
-- 幂等，可全量重放；与 init-scripts/01-schema.sql、03-seed.sql 保持同文案。

-- ---------------------------------------------------------------------------
-- 1. agent 自选分组归属
-- ---------------------------------------------------------------------------

ALTER TABLE user_watchlist_group ADD COLUMN IF NOT EXISTS owner_type VARCHAR(16) NOT NULL DEFAULT 'user';
ALTER TABLE user_watchlist_group ALTER COLUMN user_id DROP NOT NULL;

-- 平台级 agent 分组单例（服务层保证唯一，索引兜底）
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_watchlist_group_agent
    ON user_watchlist_group (owner_type) WHERE owner_type = 'agent';

-- ---------------------------------------------------------------------------
-- 2. 选股记录
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS agent_stock_selection (
    id               BIGSERIAL PRIMARY KEY,
    trade_date       DATE         NOT NULL,      -- 选入日
    stock_code       VARCHAR(10)  NOT NULL,
    reason           TEXT         NOT NULL,      -- 选股依据（引用复盘结论）
    source_result_id BIGINT,                     -- ai_analysis_result.id（当日计划生成记录）
    confidence       NUMERIC(5,4),               -- LLM 置信度（可空）
    status           VARCHAR(16)  NOT NULL DEFAULT 'active',   -- active / removed
    removed_at       TIMESTAMPTZ,
    removed_reason   TEXT,                       -- agent 剔除 / manual 人工移出
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agent_stock_selection_date_code UNIQUE (trade_date, stock_code)
);

CREATE INDEX IF NOT EXISTS idx_agent_stock_selection_code
    ON agent_stock_selection(stock_code, trade_date DESC);

COMMENT ON TABLE agent_stock_selection IS
    '交易 Agent 每日选股清单（选入/移出与依据的真相源，docs/plan/paper-trading-plan.md §10.1）';

-- ---------------------------------------------------------------------------
-- 3. 交易计划
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS agent_trade_plan (
    id                  BIGSERIAL PRIMARY KEY,
    plan_date           DATE          NOT NULL,  -- 计划日（默认当日有效）
    stock_code          VARCHAR(10)   NOT NULL,
    plan_type           VARCHAR(8)    NOT NULL,  -- buy 开仓 / sell 持仓管理
    strategy            TEXT          NOT NULL,  -- 策略描述
    buy_zone_low        NUMERIC(12,4),           -- 买点区间（buy 必填）
    buy_zone_high       NUMERIC(12,4),
    target_price        NUMERIC(12,4),           -- 止盈目标价（sell 必填）
    stop_loss           NUMERIC(12,4) NOT NULL,  -- 止损价（两类计划均必填，纪律）
    position_pct        NUMERIC(5,2)  NOT NULL,  -- 目标仓位（占总资产 %）
    status              VARCHAR(16)   NOT NULL DEFAULT 'active',
    -- 状态机：active → triggered（已触发下单）→ executed / expired（当日未触发）/ cancelled（人工取消）
    selection_id        BIGINT,                  -- 依据 agent_stock_selection（sell 计划可空）
    basis               TEXT          NOT NULL,  -- 计划依据（复盘结论/经验卡片引用）
    triggered_cl_ord_id VARCHAR(64),             -- 触发的委托（关联 paper_trade_order）
    triggered_at        TIMESTAMPTZ,
    raw                 JSONB,                   -- LLM 完整输出兜底
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agent_trade_plan_date_code_type UNIQUE (plan_date, stock_code, plan_type)
);

CREATE INDEX IF NOT EXISTS idx_agent_trade_plan_status
    ON agent_trade_plan(status, plan_date DESC);

COMMENT ON TABLE agent_trade_plan IS
    '交易 Agent 每日交易计划（盘中条件触发执行的真相源，docs/plan/paper-trading-plan.md §10.1）';

-- ---------------------------------------------------------------------------
-- 4. 定时任务 seed：agent_daily_plan_1900（北京 19:00，heavy）
--    串行在 16:00 sync / 16:10 复盘 / 16:30 涨停归因 / ≥17:45 异动之后；
--    核心输入「当日复盘解读」18:35 才生成。交易日才执行。
-- ---------------------------------------------------------------------------

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES ('agent_daily_plan_1900', 'agent-daily-plan', 'internal', '0 19 * * 1-5', true)
ON CONFLICT (task_name) DO UPDATE
SET task_type = EXCLUDED.task_type, source = EXCLUDED.source, schedule = EXCLUDED.schedule;

UPDATE collector_task SET trade_day_only = true WHERE task_name = 'agent_daily_plan_1900';

-- internal 渠道双处登记（supported_data_types + collector_channel_data_type）
UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["agent-daily-plan"]'::jsonb
WHERE source = 'internal'
  AND NOT supported_data_types @> '["agent-daily-plan"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'agent-daily-plan', 1
FROM collector_channel_config
WHERE source = 'internal'
ON CONFLICT (channel_id, data_type) DO NOTHING;
