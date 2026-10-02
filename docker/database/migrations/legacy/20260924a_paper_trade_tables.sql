-- 交易 Agent 闭环批次 1+3：模拟盘数据底座（幂等，可全量重放）
-- 委托 / 成交回报 / 资金日快照三表 + 多租户账户配置表；柜台是交易状态真相源，
-- 本地表是复盘分析与计划执行的真相源（docs/plan/paper-trading-plan.md §4/§6）。
-- 批次 3 多租户化：paper_trade_account 表 + 三表账户维度 + 委托来源标记；
-- 存量单账户时代的数据行 account 维度为 NULL（查询恒按账户过滤，不迁移不删除）。

-- ============================================================
-- 0. 账户配置表（多租户：每用户自有掘金仿真凭证，token Fernet 加密）
-- ============================================================

CREATE TABLE IF NOT EXISTS paper_trade_account (
    id                  BIGSERIAL PRIMARY KEY,
    user_id             INTEGER      NOT NULL,     -- 归属租户（users.id）
    name                VARCHAR(64)  NOT NULL,     -- 展示名（如「人工盘」「agent 盘」）
    token_encrypted     TEXT         NOT NULL,     -- 掘金仿真 token（Fernet，utils/crypto 同源）
    counter_account_id  VARCHAR(64)  NOT NULL,     -- 掘金仿真 account_id
    is_agent            BOOLEAN      NOT NULL DEFAULT FALSE,  -- agent 专属账户（全局唯一）
    is_enabled          BOOLEAN      NOT NULL DEFAULT TRUE,
    last_error          TEXT,                      -- 最近一次同步/调用错误（诊断）
    last_synced_at      TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- 同一柜台账户全平台仅允许配置一次（防 token 共享/多头配置）
    CONSTRAINT uq_paper_trade_account_counter UNIQUE (counter_account_id)
);

-- agent 指定全局唯一（部分唯一索引；服务层先清后设，此处兜底并发）
CREATE UNIQUE INDEX IF NOT EXISTS uq_paper_trade_account_agent
    ON paper_trade_account (is_agent) WHERE is_agent;

CREATE INDEX IF NOT EXISTS idx_paper_trade_account_user
    ON paper_trade_account (user_id);

-- ============================================================
-- 1. 委托表（幂等键 = 账户 + 柜台客户端委托号）
-- ============================================================

CREATE TABLE IF NOT EXISTS paper_trade_order (
    id                   BIGSERIAL PRIMARY KEY,
    cl_ord_id            VARCHAR(64)  NOT NULL,      -- 柜台 cl_ord_id（幂等键）
    trade_date           DATE         NOT NULL,      -- 业务日（柜台时间的 CN 日历日）
    symbol               VARCHAR(32)  NOT NULL,      -- 掘金格式 SHSE.600000
    stock_code           VARCHAR(10)  NOT NULL,      -- 6 位代码（关联自家行情）
    side                 SMALLINT     NOT NULL,      -- 1 买 / 2 卖
    order_type           SMALLINT     NOT NULL,      -- 1 限价 / 2 市价
    position_effect      SMALLINT     NOT NULL DEFAULT 1,
    price                NUMERIC(12,4) NOT NULL DEFAULT 0,
    volume               INT          NOT NULL,
    status               SMALLINT     NOT NULL,      -- 柜台状态原值
    ord_rej_reason       SMALLINT,
    ord_rej_reason_detail TEXT,
    counter_created_at   TIMESTAMPTZ,
    counter_updated_at   TIMESTAMPTZ,
    raw                  JSONB,                      -- 柜台原始委托（字段演进安全网）
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_paper_trade_order_cl_ord_id UNIQUE (cl_ord_id)
);

CREATE INDEX IF NOT EXISTS idx_paper_trade_order_date
    ON paper_trade_order(trade_date DESC);

-- ============================================================
-- 2. 成交回报表（幂等键 = 账户 + 柜台回报唯一标识，暂定 ex_exec_id，实抓为准后可回填）
-- ============================================================

CREATE TABLE IF NOT EXISTS paper_trade_execution (
    id                   BIGSERIAL PRIMARY KEY,
    exec_id              VARCHAR(64)  NOT NULL,      -- 柜台回报 ID（幂等键）
    cl_ord_id            VARCHAR(64)  NOT NULL,
    trade_date           DATE         NOT NULL,      -- 业务日（回报时间的 CN 日历日）
    symbol               VARCHAR(32)  NOT NULL,
    side                 SMALLINT,
    exec_type            SMALLINT,                   -- 成交/撤单等回报类型原值
    price                NUMERIC(12,4),
    volume               INT,
    turnover             NUMERIC(18,2),              -- 成交金额
    commission           NUMERIC(12,4),
    counter_created_at   TIMESTAMPTZ,
    raw                  JSONB,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_paper_trade_execution_exec_id UNIQUE (exec_id)
);

CREATE INDEX IF NOT EXISTS idx_paper_trade_execution_date
    ON paper_trade_execution(trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_paper_trade_execution_cl_ord_id
    ON paper_trade_execution(cl_ord_id);

-- ============================================================
-- 3. 资金日快照表（账户 + 一日一行，净值曲线与当日盈亏的唯一来源）
-- ============================================================

CREATE TABLE IF NOT EXISTS paper_trade_cash_snapshot (
    id                   BIGSERIAL PRIMARY KEY,
    trade_date           DATE         NOT NULL,
    nav                  NUMERIC(18,2),
    available            NUMERIC(18,2),
    balance              NUMERIC(18,2),
    cum_inout            NUMERIC(18,2),
    last_inout           NUMERIC(18,2),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_paper_trade_cash_snapshot_date UNIQUE (trade_date)
);

-- ============================================================
-- 4. 多租户化演进（幂等）：三表加账户维度 + 委托来源标记 + 唯一约束按账户收紧
--    （存量库与新建库统一走本节；账户维度可空，应用层写入恒带值，NULL 行不可见）
-- ============================================================

ALTER TABLE paper_trade_order
    ADD COLUMN IF NOT EXISTS paper_trade_account_id INTEGER,
    ADD COLUMN IF NOT EXISTS order_source VARCHAR(8) NOT NULL DEFAULT 'manual';

ALTER TABLE paper_trade_execution
    ADD COLUMN IF NOT EXISTS paper_trade_account_id INTEGER;

ALTER TABLE paper_trade_cash_snapshot
    ADD COLUMN IF NOT EXISTS paper_trade_account_id INTEGER;

-- 唯一约束从全局收紧为按账户（老库存在旧约束则替换；新库由上文建旧约束后同样走此替换）
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_paper_trade_order_cl_ord_id')
       AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_paper_trade_order_account_cl_ord_id') THEN
        ALTER TABLE paper_trade_order DROP CONSTRAINT uq_paper_trade_order_cl_ord_id;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_paper_trade_order_account_cl_ord_id') THEN
        ALTER TABLE paper_trade_order
            ADD CONSTRAINT uq_paper_trade_order_account_cl_ord_id
            UNIQUE (paper_trade_account_id, cl_ord_id);
    END IF;

    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_paper_trade_execution_exec_id')
       AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_paper_trade_execution_account_exec_id') THEN
        ALTER TABLE paper_trade_execution DROP CONSTRAINT uq_paper_trade_execution_exec_id;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_paper_trade_execution_account_exec_id') THEN
        ALTER TABLE paper_trade_execution
            ADD CONSTRAINT uq_paper_trade_execution_account_exec_id
            UNIQUE (paper_trade_account_id, exec_id);
    END IF;

    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_paper_trade_cash_snapshot_date')
       AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_paper_trade_cash_snapshot_account_date') THEN
        ALTER TABLE paper_trade_cash_snapshot DROP CONSTRAINT uq_paper_trade_cash_snapshot_date;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_paper_trade_cash_snapshot_account_date') THEN
        ALTER TABLE paper_trade_cash_snapshot
            ADD CONSTRAINT uq_paper_trade_cash_snapshot_account_date
            UNIQUE (paper_trade_account_id, trade_date);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_paper_trade_order_account_date
    ON paper_trade_order(paper_trade_account_id, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_paper_trade_execution_account_date
    ON paper_trade_execution(paper_trade_account_id, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_paper_trade_cash_snapshot_account_date
    ON paper_trade_cash_snapshot(paper_trade_account_id, trade_date DESC);

-- ============================================================
-- 5. internal 渠道登记 + 盘后同步调度（与 init-scripts/03-seed.sql 同文案）
-- ============================================================

UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["paper-trade-sync"]'::jsonb
WHERE source = 'internal'
  AND NOT supported_data_types @> '["paper-trade-sync"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'paper-trade-sync', 1
FROM collector_channel_config
WHERE source = 'internal'
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- 16:00 清算稳定且在复盘链之前，失败退避窗口充足（北京时间）
INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES
    ('paper_trade_sync_1600', 'paper-trade-sync', 'internal', '0 16 * * 1-5', true)
ON CONFLICT (task_name) DO NOTHING;
