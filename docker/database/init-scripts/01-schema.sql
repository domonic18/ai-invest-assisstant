-- ============================================================
-- AI Invest Assistant - PostgreSQL / TimescaleDB Schema
-- Version: 0.1.0
-- ============================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- 1. 基础信息域
-- ============================================================

CREATE TABLE stock_basic (
    id                 BIGSERIAL PRIMARY KEY,
    stock_code         VARCHAR(10)  NOT NULL,
    stock_name         VARCHAR(50)  NOT NULL,
    market             VARCHAR(4)   NOT NULL CHECK (market IN ('sh', 'sz', 'bj')),
    industry_l1        VARCHAR(50),
    industry_l2        VARCHAR(50),
    industry_l3        VARCHAR(50),
    listing_date       DATE,
    total_shares       BIGINT,
    circulating_shares BIGINT,
    created_at         TIMESTAMPTZ DEFAULT NOW(),
    updated_at         TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (stock_code, market)
);

CREATE INDEX idx_stock_code ON stock_basic(stock_code);
CREATE INDEX idx_stock_industry_l1 ON stock_basic(industry_l1);
CREATE INDEX idx_stock_industry_l2 ON stock_basic(industry_l2);

-- ============================================================
-- 2. 交易行情域（TimescaleDB 超表）
-- ============================================================

CREATE TABLE kline_daily (
    stock_code    VARCHAR(10)   NOT NULL,
    trade_date    DATE          NOT NULL,
    open          DECIMAL(12,3),
    high          DECIMAL(12,3),
    low           DECIMAL(12,3),
    close         DECIMAL(12,3),
    volume        BIGINT,                     -- 成交量（手）
    amount        DECIMAL(20,2),              -- 成交额（元）
    amplitude     DECIMAL(8,2),               -- 振幅%
    pct_change    DECIMAL(8,2),               -- 涨跌幅%
    turnover_rate DECIMAL(8,2),               -- 换手率%
    created_at    TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (stock_code, trade_date)
);

SELECT create_hypertable('kline_daily', 'trade_date', if_not_exists => TRUE);
CREATE INDEX idx_kline_daily_code_date ON kline_daily(stock_code, trade_date DESC);

CREATE TABLE kline_minute (
    stock_code VARCHAR(10)   NOT NULL,
    trade_time TIMESTAMPTZ   NOT NULL,
    open       DECIMAL(12,3),
    high       DECIMAL(12,3),
    low        DECIMAL(12,3),
    close      DECIMAL(12,3),
    volume     BIGINT,
    amount     DECIMAL(20,2),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (stock_code, trade_time)
);

SELECT create_hypertable('kline_minute', 'trade_time', if_not_exists => TRUE);
CREATE INDEX idx_kline_minute_code_time ON kline_minute(stock_code, trade_time DESC);

-- 集合竞价数据（盘前 9:15-9:25）
CREATE TABLE auction_data (
    id          BIGSERIAL PRIMARY KEY,
    stock_code  VARCHAR(10)    NOT NULL,
    trade_date  DATE           NOT NULL,
    match_time  TIME           NOT NULL,
    price       DECIMAL(12,3),
    volume      BIGINT,
    bid_prices  DECIMAL(12,3)[],
    bid_volumes BIGINT[],
    ask_prices  DECIMAL(12,3)[],
    ask_volumes BIGINT[],
    created_at  TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (stock_code, trade_date, match_time)
);

CREATE INDEX idx_auction_code_date_time ON auction_data(stock_code, trade_date, match_time);

-- 资金流向
CREATE TABLE fund_flow (
    stock_code       VARCHAR(10)   NOT NULL,
    trade_date       DATE          NOT NULL,
    main_net_inflow  DECIMAL(20,2),
    super_large_net  DECIMAL(20,2),
    large_net        DECIMAL(20,2),
    medium_net       DECIMAL(20,2),
    small_net        DECIMAL(20,2),
    created_at       TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (stock_code, trade_date)
);

SELECT create_hypertable('fund_flow', 'trade_date', if_not_exists => TRUE);
CREATE INDEX idx_fund_flow_code_date ON fund_flow(stock_code, trade_date DESC);

-- ============================================================
-- 3. 财务数据域
-- ============================================================

CREATE TABLE balance_sheet (
    id                  BIGSERIAL PRIMARY KEY,
    stock_code          VARCHAR(10)  NOT NULL,
    report_date         DATE         NOT NULL,
    report_type         VARCHAR(10)  NOT NULL CHECK (report_type IN ('annual', 'semi', 'q1', 'q3')),
    total_assets        DECIMAL(20,2),
    current_assets      DECIMAL(20,2),
    cash_equivalents    DECIMAL(20,2),
    accounts_receivable DECIMAL(20,2),
    inventory           DECIMAL(20,2),
    fixed_assets        DECIMAL(20,2),
    intangible_assets   DECIMAL(20,2),
    goodwill            DECIMAL(20,2),
    total_liabilities   DECIMAL(20,2),
    current_liabilities DECIMAL(20,2),
    long_term_debt      DECIMAL(20,2),
    total_equity        DECIMAL(20,2),
    paid_in_capital     DECIMAL(20,2),
    retained_earnings   DECIMAL(20,2),
    created_at          TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (stock_code, report_date)
);

CREATE INDEX idx_balance_sheet_code_date ON balance_sheet(stock_code, report_date DESC);

CREATE TABLE income_statement (
    id                  BIGSERIAL PRIMARY KEY,
    stock_code          VARCHAR(10)  NOT NULL,
    report_date         DATE         NOT NULL,
    report_type         VARCHAR(10)  NOT NULL CHECK (report_type IN ('annual', 'semi', 'q1', 'q3')),
    total_revenue       DECIMAL(20,2),
    operating_cost      DECIMAL(20,2),
    selling_expense     DECIMAL(20,2),
    admin_expense       DECIMAL(20,2),
    rd_expense          DECIMAL(20,2),
    finance_expense     DECIMAL(20,2),
    operating_profit    DECIMAL(20,2),
    net_profit          DECIMAL(20,2),
    net_profit_deducted DECIMAL(20,2),
    eps                 DECIMAL(10,4),
    created_at          TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (stock_code, report_date)
);

CREATE INDEX idx_income_statement_code_date ON income_statement(stock_code, report_date DESC);

CREATE TABLE cash_flow_statement (
    id              BIGSERIAL PRIMARY KEY,
    stock_code      VARCHAR(10)  NOT NULL,
    report_date     DATE         NOT NULL,
    report_type     VARCHAR(10)  NOT NULL CHECK (report_type IN ('annual', 'semi', 'q1', 'q3')),
    cf_operations   DECIMAL(20,2),
    cf_investing    DECIMAL(20,2),
    cf_financing    DECIMAL(20,2),
    net_cash_flow   DECIMAL(20,2),
    free_cash_flow  DECIMAL(20,2),
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (stock_code, report_date)
);

CREATE INDEX idx_cash_flow_code_date ON cash_flow_statement(stock_code, report_date DESC);

-- ============================================================
-- 4. 新闻 / 公告元数据域
-- ============================================================

CREATE TABLE news_announcement (
    id            BIGSERIAL PRIMARY KEY,
    stock_code    VARCHAR(10),
    doc_type      VARCHAR(20) NOT NULL CHECK (doc_type IN ('news', 'announcement', 'research', 'financial_report')),
    title         VARCHAR(500) NOT NULL,
    summary       TEXT,
    content       TEXT,
    source        VARCHAR(50),
    source_url    VARCHAR(1000),
    publish_date  TIMESTAMPTZ,
    sentiment     DECIMAL(5,2),              -- 情感得分 -1 ~ 1
    keywords      VARCHAR(100)[],
    industry_tags VARCHAR(50)[],
    es_id         VARCHAR(50),               -- Elasticsearch 文档 ID
    created_at    TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (source_url)
);

CREATE INDEX idx_news_code_date ON news_announcement(stock_code, publish_date DESC);
CREATE INDEX idx_news_doc_type ON news_announcement(doc_type);
CREATE INDEX idx_news_publish_date ON news_announcement(publish_date DESC);

-- ============================================================
-- 5. 产业链关系域
-- ============================================================

CREATE TABLE industry_chain_node (
    id          BIGSERIAL PRIMARY KEY,
    node_name   VARCHAR(100) NOT NULL,
    industry_l1 VARCHAR(50),
    node_type   VARCHAR(20) NOT NULL CHECK (node_type IN ('upstream', 'midstream', 'downstream')),
    description TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chain_node_industry ON industry_chain_node(industry_l1);
CREATE INDEX idx_chain_node_type ON industry_chain_node(node_type);

CREATE TABLE industry_chain_edge (
    id              BIGSERIAL PRIMARY KEY,
    source_node_id  BIGINT NOT NULL REFERENCES industry_chain_node(id) ON DELETE CASCADE,
    target_node_id  BIGINT NOT NULL REFERENCES industry_chain_node(id) ON DELETE CASCADE,
    relation_type   VARCHAR(50),
    relation_desc   TEXT,
    strength        DECIMAL(5,2) CHECK (strength >= 0 AND strength <= 100),
    source          VARCHAR(50) DEFAULT 'manual',
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (source_node_id, target_node_id, relation_type)
);

CREATE INDEX idx_chain_edge_source ON industry_chain_edge(source_node_id);
CREATE INDEX idx_chain_edge_target ON industry_chain_edge(target_node_id);

CREATE TABLE company_chain_mapping (
    id            BIGSERIAL PRIMARY KEY,
    stock_code    VARCHAR(10) NOT NULL,
    chain_node_id BIGINT NOT NULL REFERENCES industry_chain_node(id) ON DELETE CASCADE,
    position      VARCHAR(100),
    revenue_ratio DECIMAL(8,4),
    confidence    DECIMAL(5,2) CHECK (confidence >= 0 AND confidence <= 100),
    updated_at    TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (stock_code, chain_node_id)
);

CREATE INDEX idx_company_chain_code ON company_chain_mapping(stock_code);
CREATE INDEX idx_company_chain_node ON company_chain_mapping(chain_node_id);

-- ============================================================
-- 6. 文件元数据域
-- ============================================================

CREATE TABLE file_metadata (
    id             BIGSERIAL PRIMARY KEY,
    file_path      VARCHAR(500) NOT NULL UNIQUE,
    original_name  VARCHAR(500),
    file_type      VARCHAR(20) NOT NULL CHECK (file_type IN ('financial_report', 'research_report', 'announcement', 'image')),
    stock_code     VARCHAR(10),
    report_date    DATE,
    report_type    VARCHAR(20),
    broker         VARCHAR(100),
    file_size      BIGINT,
    md5_hash       VARCHAR(32),
    download_url   VARCHAR(1000),
    download_count INT DEFAULT 0,
    uploaded_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_file_type ON file_metadata(file_type);
CREATE INDEX idx_file_stock_report ON file_metadata(stock_code, report_date);

-- ============================================================
-- 7. 用户 / 系统域
-- ============================================================

CREATE TABLE users (
    id            BIGSERIAL PRIMARY KEY,
    username      VARCHAR(50)  UNIQUE NOT NULL,
    email         VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20)  DEFAULT 'user' CHECK (role IN ('user', 'admin', 'analyst')),
    is_active     BOOLEAN      DEFAULT true,
    last_login_at TIMESTAMPTZ,
    created_at    TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);

CREATE TABLE user_watchlist (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    stock_code VARCHAR(10) NOT NULL,
    tags       VARCHAR(50)[],
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (user_id, stock_code)
);

CREATE INDEX idx_watchlist_user ON user_watchlist(user_id);

-- ============================================================
-- 8. AI 分析结果域
-- ============================================================

CREATE TABLE ai_analysis_result (
    id           BIGSERIAL PRIMARY KEY,
    analysis_id  UUID DEFAULT uuid_generate_v4(),
    skill_id     VARCHAR(50) NOT NULL,
    stock_code   VARCHAR(10),
    input_hash   VARCHAR(64),                 -- 输入参数哈希，用于幂等/缓存
    prompt_id    VARCHAR(50),
    model        VARCHAR(50),
    raw_output   TEXT,
    structured_output JSONB,
    confidence   DECIMAL(5,2),
    latency_ms   INT,
    status       VARCHAR(20) DEFAULT 'success' CHECK (status IN ('success', 'failed', 'cached')),
    error_msg    TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ai_skill_code ON ai_analysis_result(skill_id, stock_code);
CREATE INDEX idx_ai_created_at ON ai_analysis_result(created_at DESC);

-- ============================================================
-- 9. 采集任务域
-- ============================================================

CREATE TABLE collector_task (
    id              BIGSERIAL PRIMARY KEY,
    task_name       VARCHAR(100) NOT NULL UNIQUE,
    task_type       VARCHAR(50)  NOT NULL,
    source          VARCHAR(50)  NOT NULL,
    schedule        VARCHAR(100),             -- cron 表达式或描述
    is_active       BOOLEAN      DEFAULT true,
    last_run_at     TIMESTAMPTZ,
    last_status     VARCHAR(20)  DEFAULT 'pending' CHECK (last_status IN ('pending', 'running', 'success', 'failed')),
    last_error      TEXT,
    created_at      TIMESTAMPTZ  DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX idx_collector_task_active ON collector_task(is_active);

CREATE TABLE collector_log (
    id          BIGSERIAL PRIMARY KEY,
    task_id     BIGINT REFERENCES collector_task(id) ON DELETE SET NULL,
    task_name   VARCHAR(100),
    source      VARCHAR(50),
    status      VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'running', 'success', 'partial', 'failed', 'skipped')),
    started_at  TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    records_count INT DEFAULT 0,
    error_msg   TEXT,
    metadata    JSONB
);

CREATE INDEX idx_collector_log_task ON collector_log(task_id, started_at DESC);
CREATE INDEX idx_collector_log_started ON collector_log(started_at DESC);

-- ============================================================
-- 10. LLM 配置域（后台管理）
-- ============================================================

CREATE TABLE llm_configs (
    id                  BIGSERIAL PRIMARY KEY,
    name                VARCHAR(100) NOT NULL,
    provider            VARCHAR(20)  NOT NULL,
    base_url            VARCHAR(500) NOT NULL,
    api_key_encrypted   TEXT         NOT NULL,
    model_name          VARCHAR(100) NOT NULL,
    is_default          BOOLEAN      NOT NULL DEFAULT FALSE,
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    extra               JSONB        NOT NULL DEFAULT '{}'::jsonb,
    last_tested_at      TIMESTAMPTZ,
    last_test_status    VARCHAR(20),
    last_test_error     TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_llm_configs_active ON llm_configs(provider) WHERE is_active = TRUE;

CREATE UNIQUE INDEX ux_llm_configs_default
    ON llm_configs(is_default) WHERE is_default = TRUE;

-- ============================================================
-- 11. 采集渠道配置域（后台管理）
-- ============================================================

CREATE TABLE collector_channel_configs (
    id                  BIGSERIAL PRIMARY KEY,
    source              VARCHAR(50)  NOT NULL UNIQUE,
    name                VARCHAR(100) NOT NULL,
    base_url            VARCHAR(500),
    api_key_encrypted   TEXT,
    is_enabled          BOOLEAN      NOT NULL DEFAULT TRUE,
    supported_data_types JSONB       NOT NULL DEFAULT '[]'::jsonb,
    extra               JSONB        NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_collector_channel_enabled ON collector_channel_configs(is_enabled);
CREATE INDEX idx_collector_channel_supported_types ON collector_channel_configs USING GIN(supported_data_types);

-- ============================================================
-- 12. 扩展：公司概况、公告/研报扩展字段、板块资金、龙虎榜、宏观经济
-- ============================================================

ALTER TABLE stock_basic
    ADD COLUMN IF NOT EXISTS full_name VARCHAR(200),
    ADD COLUMN IF NOT EXISTS legal_person VARCHAR(100),
    ADD COLUMN IF NOT EXISTS website VARCHAR(200),
    ADD COLUMN IF NOT EXISTS registered_capital DECIMAL(20,2),
    ADD COLUMN IF NOT EXISTS business_scope TEXT,
    ADD COLUMN IF NOT EXISTS province VARCHAR(50),
    ADD COLUMN IF NOT EXISTS city VARCHAR(50);

ALTER TABLE news_announcement
    ADD COLUMN IF NOT EXISTS extra JSONB DEFAULT '{}'::jsonb;

-- 扩展 doc_type 枚举以支持财报采集
DO $$
BEGIN
    ALTER TABLE news_announcement
        DROP CONSTRAINT IF EXISTS news_announcement_doc_type_check;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'news_announcement_doc_type_check'
          AND conrelid = 'news_announcement'::regclass
    ) THEN
        ALTER TABLE news_announcement
            ADD CONSTRAINT news_announcement_doc_type_check
            CHECK (doc_type IN ('news', 'announcement', 'research', 'financial_report'));
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS sector_fund_flow (
    sector_code      VARCHAR(20)  NOT NULL,
    sector_name      VARCHAR(100) NOT NULL,
    sector_type      VARCHAR(20)  NOT NULL CHECK (sector_type IN ('industry','concept','region')),
    trade_date       DATE         NOT NULL,
    change_pct       DECIMAL(8,2),
    main_net_inflow  DECIMAL(20,2),
    super_large_net  DECIMAL(20,2),
    large_net        DECIMAL(20,2),
    medium_net       DECIMAL(20,2),
    small_net        DECIMAL(20,2),
    top_stock_code   VARCHAR(10),
    top_stock_name   VARCHAR(100),
    created_at       TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (sector_code, sector_type, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_sector_fund_flow_date ON sector_fund_flow(trade_date DESC);

CREATE TABLE IF NOT EXISTS dragon_list (
    id          BIGSERIAL PRIMARY KEY,
    trade_date  DATE         NOT NULL,
    stock_code  VARCHAR(10)  NOT NULL,
    stock_name  VARCHAR(100),
    rank_reason VARCHAR(500),
    close_price DECIMAL(12,3),
    change_pct  DECIMAL(8,2),
    net_buy_amount DECIMAL(20,2),
    created_at  TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (trade_date, stock_code, rank_reason)
);
CREATE INDEX IF NOT EXISTS idx_dragon_list_date ON dragon_list(trade_date DESC);

CREATE TABLE IF NOT EXISTS macro_indicator (
    id           BIGSERIAL PRIMARY KEY,
    indicator_name VARCHAR(20) NOT NULL,
    period_type  VARCHAR(20) NOT NULL,
    publish_date DATE        NOT NULL,
    value        DECIMAL(12,4),
    value_yoy    DECIMAL(8,4),
    value_mom    DECIMAL(8,4),
    source       VARCHAR(50),
    created_at   TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (indicator_name, period_type, publish_date)
);
CREATE INDEX IF NOT EXISTS idx_macro_indicator_name_date ON macro_indicator(indicator_name, publish_date DESC);

-- ============================================================
-- 13. 扩展：IPO 信息、基金持仓
-- ============================================================

CREATE TABLE IF NOT EXISTS ipo_info (
    id                       BIGSERIAL PRIMARY KEY,
    stock_code               VARCHAR(10)  NOT NULL,
    stock_name               VARCHAR(100),
    listing_date             DATE,
    subscription_date        DATE,
    issue_price              DECIMAL(12,3),
    total_issue_quantity     DECIMAL(20,2),
    issue_pe_ratio           DECIMAL(12,2),
    online_winning_rate      DECIMAL(12,4),
    lottery_result_date      DATE,
    winning_announcement_date DATE,
    payment_date             DATE,
    online_subscription_limit DECIMAL(20,2),
    online_issue_quantity    DECIMAL(20,2),
    source                   VARCHAR(50),
    created_at               TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (stock_code, subscription_date)
);
CREATE INDEX IF NOT EXISTS idx_ipo_info_listing_date ON ipo_info(listing_date DESC);
CREATE INDEX IF NOT EXISTS idx_ipo_info_subscription_date ON ipo_info(subscription_date DESC);

CREATE TABLE IF NOT EXISTS fund_holdings (
    id                    BIGSERIAL PRIMARY KEY,
    stock_code            VARCHAR(10)  NOT NULL,
    stock_name            VARCHAR(100),
    report_date           DATE         NOT NULL,
    holding_fund_count    INT,
    total_holding_quantity BIGINT,
    holding_market_value  DECIMAL(20,2),
    holding_change        VARCHAR(20),
    holding_change_quantity BIGINT,
    holding_change_ratio  DECIMAL(8,2),
    source                VARCHAR(50),
    created_at            TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (stock_code, report_date)
);
CREATE INDEX IF NOT EXISTS idx_fund_holdings_report_date ON fund_holdings(report_date DESC);
CREATE INDEX IF NOT EXISTS idx_fund_holdings_stock_code ON fund_holdings(stock_code);

-- ============================================================
-- 14. 涨停股池（每日复盘：涨停板 / 连板天梯）
-- ============================================================

CREATE TABLE IF NOT EXISTS limit_up_pool (
    id                 BIGSERIAL PRIMARY KEY,
    trade_date         DATE         NOT NULL,
    stock_code         VARCHAR(10)  NOT NULL,
    stock_name         VARCHAR(100),
    change_pct         DECIMAL(8,2),
    latest_price       DECIMAL(12,3),
    turnover_rate      DECIMAL(8,2),
    sealed_amount      DECIMAL(20,2),
    first_seal_time    VARCHAR(10),
    last_seal_time     VARCHAR(10),
    break_count        INT,
    limit_stat         VARCHAR(20),
    consecutive_boards INT,
    industry           VARCHAR(100),
    source             VARCHAR(50),
    created_at         TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (trade_date, stock_code)
);
CREATE INDEX IF NOT EXISTS idx_limit_up_pool_date ON limit_up_pool(trade_date DESC);
