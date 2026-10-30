-- 多周期复盘 B1（docs/requirement/09-multi-period-review-requirement.md §5）：
-- 新增 paper_trade_position_snapshot —— 每日持仓快照，账户 + 交易日 + 标的，
-- 是长周期复盘收益归因（个股/行业贡献、期初/期末仓位）的数据源。
-- 写入方式：盘后同步按 (账户, 交易日) 全量覆盖（先删后插，平仓标的不留行）；
-- 历史区间由委托/成交重放重建（services/trading/position_replay.py）。
-- 幂等：CREATE TABLE IF NOT EXISTS + 约束内联；重放无副作用。

CREATE TABLE IF NOT EXISTS paper_trade_position_snapshot (
    id                     BIGSERIAL PRIMARY KEY,
    paper_trade_account_id INTEGER      NOT NULL,
    trade_date             DATE         NOT NULL,
    symbol                 VARCHAR(32),               -- 掘金格式 SHSE.600000（可为空：重放行仅知 6 位代码）
    stock_code             VARCHAR(10)  NOT NULL,     -- 6 位代码（关联自家行情）
    volume                 INT          NOT NULL,
    available_volume       INT,
    avg_price              NUMERIC(12,4),
    last_price             NUMERIC(12,4),
    market_value           NUMERIC(18,2),
    profit                 NUMERIC(18,2),
    profit_rate            NUMERIC(12,4),
    weight                 NUMERIC(8,4),              -- 占当日持仓市值合计的百分比
    created_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_paper_trade_position_snapshot_account_date_code
        UNIQUE (paper_trade_account_id, trade_date, stock_code)
);

CREATE INDEX IF NOT EXISTS idx_paper_trade_position_snapshot_account_date
    ON paper_trade_position_snapshot (paper_trade_account_id, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_paper_trade_position_snapshot_code
    ON paper_trade_position_snapshot (stock_code);
