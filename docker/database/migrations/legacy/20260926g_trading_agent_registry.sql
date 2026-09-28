-- Agent Hub 多 Agent 基座（docs/plan/agent-hub-plan.md D21-D23）。
-- trading_agent 注册表取代 trading_agent_config 单例（身份/介绍/模型绑定/风控/总闸）；
-- paper_trade_account 以 agent_key 取代 is_agent（每 Agent 绑定专属账户）；
-- 三张 agent 表 + agent 自选分组加 agent 维度并重建唯一约束；
-- assistant_session.agent_type 加宽并迁移 'trading' → 'short-line'。
-- 本批仅 short-line 激活，long-line / m60 注册为 planned（总览幽灵节点展示）。
-- 幂等，可全量重放；与 init-scripts/01-schema.sql、03-seed.sql 保持同文案。

-- ---------------------------------------------------------------------------
-- 1. trading_agent 注册表（D21：取代 trading_agent_config 单例）
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS trading_agent (
    agent_key              VARCHAR(32)   PRIMARY KEY,                  -- URL 安全自然键
    name                   VARCHAR(64)   NOT NULL,                     -- 展示名
    tagline                VARCHAR(128)  NOT NULL DEFAULT '',          -- 一句话定位
    strategy_desc          TEXT          NOT NULL DEFAULT '',          -- 策略介绍（介绍卡/预告卡）
    style_desc             VARCHAR(64)   NOT NULL DEFAULT '',          -- 风格标签
    llm_config_id          BIGINT,                                     -- 对话/结构化输出模型；空 = 默认 chat
    methodology_source_id  BIGINT,                                     -- 方法论知识源（kb_source.id）；空 = 未启用
    risk_max_position_pct  NUMERIC(5,2)  NOT NULL DEFAULT 20,          -- 单票市值 ≤ 总资产 %
    risk_max_total_pct     NUMERIC(5,2)  NOT NULL DEFAULT 80,          -- 总持仓市值 ≤ 总资产 %
    risk_max_daily_orders  INTEGER       NOT NULL DEFAULT 10,          -- 单日下单笔数上限
    auto_exec_enabled      BOOLEAN       NOT NULL DEFAULT TRUE,        -- 盘中自主执行总闸
    status                 VARCHAR(16)   NOT NULL DEFAULT 'active',    -- active / planned / disabled
    sort_order             INTEGER       NOT NULL DEFAULT 0,           -- 总览排布
    prompt_id              VARCHAR(64)   NOT NULL DEFAULT 'trading_agent',  -- prompts/agents/<prompt_id>.yaml
    accent_color           VARCHAR(16)   NOT NULL DEFAULT '#3b82f6',   -- 总览节点主色
    created_at             TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_trading_agent_llm_config
        FOREIGN KEY (llm_config_id) REFERENCES llm_config (id) ON DELETE SET NULL,
    CONSTRAINT fk_trading_agent_methodology_source
        FOREIGN KEY (methodology_source_id) REFERENCES kb_source (id) ON DELETE SET NULL,
    CONSTRAINT chk_trading_agent_status
        CHECK (status IN ('active', 'planned', 'disabled')),
    CONSTRAINT chk_trading_agent_position_pct
        CHECK (risk_max_position_pct >= 0 AND risk_max_position_pct <= 100),
    CONSTRAINT chk_trading_agent_total_pct
        CHECK (risk_max_total_pct >= 0 AND risk_max_total_pct <= 100),
    CONSTRAINT chk_trading_agent_daily_orders
        CHECK (risk_max_daily_orders >= 1)
);

COMMENT ON TABLE trading_agent IS
    '交易 Agent 注册表：身份/介绍/模型绑定/风控/总闸（docs/plan/agent-hub-plan.md D21）';

-- 原单例配置迁移为 short-line（源表存在才执行，随后删表——重放安全）
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'trading_agent_config') THEN
        INSERT INTO trading_agent (agent_key, name, tagline, strategy_desc, style_desc,
            llm_config_id, methodology_source_id, risk_max_position_pct, risk_max_total_pct,
            risk_max_daily_orders, auto_exec_enabled, status, sort_order)
        SELECT 'short-line', '短线猎手', '趋势短线：顺势而为，快进快出',
               '基于当日复盘解读与涨停归因的趋势短线策略：主线板块选股，回踩买点区间接回，破位止损。', '进取',
               c.llm_config_id, c.methodology_source_id, c.risk_max_position_pct, c.risk_max_total_pct,
               c.risk_max_daily_orders, c.auto_exec_enabled, 'active', 1
        FROM trading_agent_config c
        WHERE NOT EXISTS (SELECT 1 FROM trading_agent WHERE agent_key = 'short-line');
        DROP TABLE trading_agent_config;
    END IF;
END $$;

-- planned 展示行（长线 / M60：总览幽灵节点，不参与执行）
INSERT INTO trading_agent (agent_key, name, tagline, strategy_desc, style_desc, status, sort_order, accent_color)
VALUES
    ('long-line', '长线舵手', '基本面长线：低频布局，穿越周期',
     '基本面与产业趋势驱动的长线布局策略（规划中，未激活）。', '稳健', 'planned', 2, '#10b981'),
    ('m60', '60分钟波段', 'M60 结构波段：形态驱动，波段进退',
     '60 分钟级别结构形态驱动的波段策略（规划中，未激活）。', '灵活', 'planned', 3, '#f59e0b')
ON CONFLICT (agent_key) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 2. paper_trade_account：is_agent → agent_key（D22）
-- ---------------------------------------------------------------------------

DROP INDEX IF EXISTS uq_paper_trade_account_agent;
ALTER TABLE paper_trade_account
    ADD COLUMN IF NOT EXISTS agent_key VARCHAR(32) REFERENCES trading_agent (agent_key) ON DELETE RESTRICT;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'paper_trade_account' AND column_name = 'is_agent') THEN
        UPDATE paper_trade_account SET agent_key = 'short-line' WHERE is_agent AND agent_key IS NULL;
        ALTER TABLE paper_trade_account DROP COLUMN is_agent;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_paper_trade_account_agent_key
    ON paper_trade_account (agent_key) WHERE agent_key IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 3. 三张 agent 表 + agent 自选分组加 agent 维度（D23）
-- ---------------------------------------------------------------------------

ALTER TABLE agent_stock_selection ADD COLUMN IF NOT EXISTS agent_key VARCHAR(32);
UPDATE agent_stock_selection SET agent_key = 'short-line' WHERE agent_key IS NULL;
ALTER TABLE agent_stock_selection ALTER COLUMN agent_key SET NOT NULL;
ALTER TABLE agent_stock_selection DROP CONSTRAINT IF EXISTS fk_agent_stock_selection_agent;
ALTER TABLE agent_stock_selection ADD CONSTRAINT fk_agent_stock_selection_agent
    FOREIGN KEY (agent_key) REFERENCES trading_agent (agent_key) ON DELETE RESTRICT;
ALTER TABLE agent_stock_selection DROP CONSTRAINT IF EXISTS uq_agent_stock_selection_date_code;
ALTER TABLE agent_stock_selection ADD CONSTRAINT uq_agent_stock_selection_agent_date_code
    UNIQUE (agent_key, trade_date, stock_code);

ALTER TABLE agent_trade_plan ADD COLUMN IF NOT EXISTS agent_key VARCHAR(32);
UPDATE agent_trade_plan SET agent_key = 'short-line' WHERE agent_key IS NULL;
ALTER TABLE agent_trade_plan ALTER COLUMN agent_key SET NOT NULL;
ALTER TABLE agent_trade_plan DROP CONSTRAINT IF EXISTS fk_agent_trade_plan_agent;
ALTER TABLE agent_trade_plan ADD CONSTRAINT fk_agent_trade_plan_agent
    FOREIGN KEY (agent_key) REFERENCES trading_agent (agent_key) ON DELETE RESTRICT;
ALTER TABLE agent_trade_plan DROP CONSTRAINT IF EXISTS uq_agent_trade_plan_date_code_type;
ALTER TABLE agent_trade_plan ADD CONSTRAINT uq_agent_trade_plan_agent_date_code_type
    UNIQUE (agent_key, plan_date, stock_code, plan_type);

ALTER TABLE agent_memory ADD COLUMN IF NOT EXISTS agent_key VARCHAR(32);
UPDATE agent_memory SET agent_key = 'short-line' WHERE agent_key IS NULL;
ALTER TABLE agent_memory ALTER COLUMN agent_key SET NOT NULL;
ALTER TABLE agent_memory DROP CONSTRAINT IF EXISTS fk_agent_memory_agent;
ALTER TABLE agent_memory ADD CONSTRAINT fk_agent_memory_agent
    FOREIGN KEY (agent_key) REFERENCES trading_agent (agent_key) ON DELETE RESTRICT;
ALTER TABLE agent_memory DROP CONSTRAINT IF EXISTS uq_agent_memory_source_title;
ALTER TABLE agent_memory ADD CONSTRAINT uq_agent_memory_agent_source_title
    UNIQUE (agent_key, source_result_id, title);

-- agent 自选分组：平台级单例 → 每 Agent 一组
ALTER TABLE user_watchlist_group ADD COLUMN IF NOT EXISTS agent_key VARCHAR(32)
    REFERENCES trading_agent (agent_key) ON DELETE CASCADE;
UPDATE user_watchlist_group SET agent_key = 'short-line'
    WHERE owner_type = 'agent' AND agent_key IS NULL;
DROP INDEX IF EXISTS uq_user_watchlist_group_agent;
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_watchlist_group_agent_key
    ON user_watchlist_group (owner_type, agent_key)
    WHERE owner_type = 'agent' AND agent_key IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 4. assistant_session.agent_type：加宽 + 'trading' → 'short-line'（D25）
-- ---------------------------------------------------------------------------

ALTER TABLE assistant_session ALTER COLUMN agent_type TYPE VARCHAR(32);
UPDATE assistant_session SET agent_type = 'short-line' WHERE agent_type = 'trading';
