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
    industry_level_1        VARCHAR(50),
    industry_level_2        VARCHAR(50),
    industry_level_3        VARCHAR(50),
    listing_date       DATE,
    total_shares       BIGINT,
    circulating_shares BIGINT,
    created_at         TIMESTAMPTZ DEFAULT NOW(),
    updated_at         TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (stock_code, market)
);

CREATE INDEX idx_stock_code ON stock_basic(stock_code);
CREATE INDEX idx_stock_industry_level_1 ON stock_basic(industry_level_1);
CREATE INDEX idx_stock_industry_level_2 ON stock_basic(industry_level_2);

-- ============================================================
-- 2. 交易行情域（TimescaleDB 超表）
-- ============================================================

CREATE TABLE quote_kline_stock_daily (
    stock_code    VARCHAR(10)   NOT NULL,
    trade_date    DATE          NOT NULL,
    open          DECIMAL(12,3),
    high          DECIMAL(12,3),
    low           DECIMAL(12,3),
    close         DECIMAL(12,3),
    volume        BIGINT,                     -- 成交量（手）
    amount        DECIMAL(20,2),              -- 成交额（元）
    amplitude     DECIMAL(8,2),               -- 振幅%
    change_pct    DECIMAL(8,2),               -- 涨跌幅%
    turnover_rate DECIMAL(8,2),               -- 换手率%
    created_at    TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (stock_code, trade_date)
);

SELECT create_hypertable('quote_kline_stock_daily', 'trade_date', chunk_time_interval => INTERVAL '1 year', if_not_exists => TRUE);
CREATE INDEX idx_quote_kline_stock_daily_code_date ON quote_kline_stock_daily(stock_code, trade_date DESC);

CREATE TABLE quote_kline_stock_minute (
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

SELECT create_hypertable('quote_kline_stock_minute', 'trade_time', if_not_exists => TRUE);
CREATE INDEX idx_quote_kline_stock_minute_code_time ON quote_kline_stock_minute(stock_code, trade_time DESC);

-- 集合竞价数据（盘前 9:15-9:25）
CREATE TABLE quote_auction_stock (
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

CREATE INDEX idx_quote_auction_stock_code_date_time ON quote_auction_stock(stock_code, trade_date, match_time);

-- 资金流向
CREATE TABLE capital_fund_flow_stock (
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

SELECT create_hypertable('capital_fund_flow_stock', 'trade_date', if_not_exists => TRUE);
CREATE INDEX idx_capital_fund_flow_stock_code_date ON capital_fund_flow_stock(stock_code, trade_date DESC);

-- ============================================================
-- 3. 财务数据域
-- ============================================================

CREATE TABLE financial_balance_sheet (
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

CREATE INDEX idx_financial_balance_sheet_code_date ON financial_balance_sheet(stock_code, report_date DESC);

CREATE TABLE financial_income_statement (
    id                  BIGSERIAL PRIMARY KEY,
    stock_code          VARCHAR(10)  NOT NULL,
    report_date         DATE         NOT NULL,
    report_type         VARCHAR(10)  NOT NULL CHECK (report_type IN ('annual', 'semi', 'q1', 'q3')),
    total_revenue       DECIMAL(20,2),
    operating_cost      DECIMAL(20,2),
    selling_expense     DECIMAL(20,2),
    admin_expense       DECIMAL(20,2),
    research_development_expense DECIMAL(20,2),
    finance_expense     DECIMAL(20,2),
    operating_profit    DECIMAL(20,2),
    net_profit          DECIMAL(20,2),
    net_profit_deducted DECIMAL(20,2),
    eps                 DECIMAL(10,4),
    created_at          TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (stock_code, report_date)
);

CREATE INDEX idx_financial_income_statement_code_date ON financial_income_statement(stock_code, report_date DESC);

CREATE TABLE financial_cash_flow_statement (
    id              BIGSERIAL PRIMARY KEY,
    stock_code      VARCHAR(10)  NOT NULL,
    report_date     DATE         NOT NULL,
    report_type     VARCHAR(10)  NOT NULL CHECK (report_type IN ('annual', 'semi', 'q1', 'q3')),
    cash_flow_from_operations   DECIMAL(20,2),
    cash_flow_from_investing    DECIMAL(20,2),
    cash_flow_from_financing    DECIMAL(20,2),
    net_cash_flow   DECIMAL(20,2),
    free_cash_flow  DECIMAL(20,2),
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (stock_code, report_date)
);

CREATE INDEX idx_financial_cash_flow_statement_code_date ON financial_cash_flow_statement(stock_code, report_date DESC);

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
    elasticsearch_doc_id VARCHAR(50),               -- Elasticsearch 文档 ID
    created_at    TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (source_url)
);

CREATE INDEX idx_news_code_date ON news_announcement(stock_code, publish_date DESC);
CREATE INDEX idx_news_doc_type ON news_announcement(doc_type);
CREATE INDEX idx_news_publish_date ON news_announcement(publish_date DESC);

-- ============================================================
-- 5. 产业链关系域
-- ============================================================

CREATE TABLE industry_chain_analysis_version (
    id               BIGSERIAL PRIMARY KEY,
    industry         VARCHAR(50)  NOT NULL,
    version_number   INT          NOT NULL,
    label            VARCHAR(100),
    status           VARCHAR(20)  NOT NULL DEFAULT 'success'
                     CONSTRAINT chk_industry_chain_analysis_version_status
                     CHECK (status IN ('success', 'failed')),
    snapshot         JSONB        NOT NULL,
    -- FK 至 ai_analysis_result 在该表创建后通过 ALTER TABLE 添加
    ai_result_id     BIGINT,
    model            VARCHAR(50),
    node_count       INT,
    company_count    INT,
    error_message    TEXT,
    created_by       VARCHAR(20)  NOT NULL DEFAULT 'manual',
    created_at       TIMESTAMPTZ  DEFAULT NOW(),
    user_id          BIGINT       NOT NULL DEFAULT 0,

    CONSTRAINT uq_industry_chain_analysis_version_user_industry_version_number
        UNIQUE (user_id, industry, version_number)
);

CREATE INDEX idx_industry_chain_analysis_version_industry
    ON industry_chain_analysis_version(industry, created_at DESC);
CREATE INDEX idx_industry_chain_analysis_version_user_industry
    ON industry_chain_analysis_version(user_id, industry, created_at DESC);

CREATE TABLE industry_chain_node (
    id          BIGSERIAL PRIMARY KEY,
    node_name   VARCHAR(100) NOT NULL,
    industry    VARCHAR(50),
    node_type   VARCHAR(20) NOT NULL CHECK (node_type IN ('upstream', 'midstream', 'downstream')),
    description TEXT,
    version_id  BIGINT REFERENCES industry_chain_analysis_version(id) ON DELETE CASCADE,
    avg_gross_margin DECIMAL(8,2),
    revenue_growth   DECIMAL(8,2),
    research_and_development_ratio DECIMAL(8,2),
    bargaining_power DECIMAL(5,2),
    localization_rate DECIMAL(5,2),
    technology_barrier VARCHAR(10),
    bottleneck_indicators TEXT[],
    recent_breakthroughs  TEXT[],
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chain_node_industry ON industry_chain_node(industry);
CREATE INDEX idx_chain_node_type ON industry_chain_node(node_type);
CREATE INDEX idx_industry_chain_node_version ON industry_chain_node(version_id);

CREATE TABLE industry_chain_edge (
    id              BIGSERIAL PRIMARY KEY,
    source_node_id  BIGINT NOT NULL REFERENCES industry_chain_node(id) ON DELETE CASCADE,
    target_node_id  BIGINT NOT NULL REFERENCES industry_chain_node(id) ON DELETE CASCADE,
    relation_type   VARCHAR(50),
    relation_description   TEXT,
    strength        DECIMAL(5,2) CHECK (strength >= 0 AND strength <= 100),
    criticality     VARCHAR(10),
    data_source   VARCHAR(50) DEFAULT 'manual',
    version_id    BIGINT REFERENCES industry_chain_analysis_version(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (source_node_id, target_node_id, relation_type)
);

CREATE INDEX idx_chain_edge_source ON industry_chain_edge(source_node_id);
CREATE INDEX idx_chain_edge_target ON industry_chain_edge(target_node_id);
CREATE INDEX idx_industry_chain_edge_version ON industry_chain_edge(version_id);

CREATE TABLE industry_chain_company_mapping (
    id            BIGSERIAL PRIMARY KEY,
    stock_code    VARCHAR(10) NOT NULL,
    chain_node_id BIGINT NOT NULL REFERENCES industry_chain_node(id) ON DELETE CASCADE,
    chain_position      VARCHAR(100),
    revenue_ratio DECIMAL(8,4),
    confidence    DECIMAL(5,2) CHECK (confidence >= 0 AND confidence <= 100),
    version_id    BIGINT REFERENCES industry_chain_analysis_version(id) ON DELETE CASCADE,
    updated_at    TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (stock_code, chain_node_id)
);

CREATE INDEX idx_company_chain_code ON industry_chain_company_mapping(stock_code);
CREATE INDEX idx_company_chain_node ON industry_chain_company_mapping(chain_node_id);
CREATE INDEX idx_industry_chain_company_mapping_version
    ON industry_chain_company_mapping(version_id);

-- 股票-概念映射表（同花顺概念成分股）
CREATE TABLE mapping_stock_concept (
    id            BIGSERIAL PRIMARY KEY,
    stock_code    VARCHAR(10)  NOT NULL,
    concept_code  VARCHAR(20)  NOT NULL,
    concept_name  VARCHAR(100) NOT NULL,
    source        VARCHAR(50)  DEFAULT 'ths' NOT NULL,
    updated_at    TIMESTAMPTZ  DEFAULT NOW(),

    CONSTRAINT uq_mapping_stock_concept_stock_concept
        UNIQUE (stock_code, concept_code)
);

CREATE INDEX idx_mapping_stock_concept_stock_code
    ON mapping_stock_concept(stock_code);
CREATE INDEX idx_mapping_stock_concept_concept_code
    ON mapping_stock_concept(concept_code);

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
    summary        TEXT,
    download_url   VARCHAR(1000),
    download_count INT DEFAULT 0,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_file_type ON file_metadata(file_type);
CREATE INDEX idx_file_stock_report ON file_metadata(stock_code, report_date);

-- ============================================================
-- 7. 用户 / 系统域
-- ============================================================

CREATE TABLE "user" (
    id            BIGSERIAL PRIMARY KEY,
    username      VARCHAR(50)  UNIQUE NOT NULL,
    email         VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20)  DEFAULT 'user' CHECK (role IN ('user', 'admin', 'analyst')),
    is_active     BOOLEAN      DEFAULT true,
    settings      JSONB        DEFAULT '{}'::jsonb,
    last_login_at TIMESTAMPTZ,
    created_at    TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX idx_user_email ON "user"(email);

CREATE TABLE user_watchlist (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    stock_code VARCHAR(10) NOT NULL,
    tags       VARCHAR(50)[],
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (user_id, stock_code)
);

CREATE INDEX idx_watchlist_user ON user_watchlist(user_id);

-- ============================================================
-- 7.5 对话助手域
-- ============================================================

CREATE TABLE assistant_session (
    id              UUID PRIMARY KEY,                -- 兼作 Agent Protocol thread_id
    user_id         BIGINT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    title           VARCHAR(128),
    last_message_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_assistant_session_user ON assistant_session (user_id, last_message_at DESC);

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
CREATE INDEX idx_ai_skill_hash ON ai_analysis_result(skill_id, input_hash);
CREATE INDEX idx_ai_created_at ON ai_analysis_result(created_at DESC);

ALTER TABLE industry_chain_analysis_version
    ADD CONSTRAINT fk_industry_chain_analysis_version_ai_result
    FOREIGN KEY (ai_result_id) REFERENCES ai_analysis_result(id) ON DELETE SET NULL;

CREATE TABLE user_market_review (
    id                BIGSERIAL PRIMARY KEY,
    user_id           BIGINT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    trade_date        DATE NOT NULL,
    sections          JSONB NOT NULL DEFAULT '{}',
    model             VARCHAR(50),
    generated_at      TIMESTAMPTZ,
    base_review_id    BIGINT REFERENCES ai_analysis_result(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (user_id, trade_date)
);

CREATE INDEX idx_user_market_review_user_date ON user_market_review(user_id, trade_date);
CREATE INDEX idx_user_market_review_trade_date ON user_market_review(trade_date);

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
    updated_at      TIMESTAMPTZ  DEFAULT NOW(),
    queue           VARCHAR(20)               -- 任务路由队列覆盖（空则按 task_type 解析）
);

CREATE INDEX idx_collector_task_active ON collector_task(is_active);
CREATE INDEX idx_collector_task_active_schedule ON collector_task(is_active, schedule) WHERE is_active = TRUE;

CREATE TABLE collector_log (
    id          BIGSERIAL PRIMARY KEY,
    task_id     BIGINT REFERENCES collector_task(id) ON DELETE SET NULL,
    task_name   VARCHAR(100),
    source      VARCHAR(50),
    status      VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'running', 'success', 'partial', 'failed', 'skipped')),
    celery_task_id VARCHAR(64),
    started_at  TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    records_count INT DEFAULT 0,
    error_msg   TEXT,
    metadata    JSONB,

    CONSTRAINT uq_collector_log_celery_task_id UNIQUE (celery_task_id)
);

CREATE INDEX idx_collector_log_task ON collector_log(task_id, started_at DESC);
CREATE INDEX idx_collector_log_started ON collector_log(started_at DESC);
CREATE INDEX idx_collector_log_celery_task_id ON collector_log(celery_task_id);
CREATE INDEX idx_collector_log_status_started_at ON collector_log(status, started_at DESC);
CREATE INDEX idx_collector_log_task_name ON collector_log(task_name);

CREATE TABLE collector_dead_letter (
    id            SERIAL PRIMARY KEY,
    task_name     VARCHAR(100) NOT NULL,
    source        VARCHAR(50),
    payload       JSONB NOT NULL,
    celery_task_id VARCHAR(64),
    collector_log_id INT,
    error_msg     TEXT,
    retry_count   INT NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_collector_dead_letter_task_name ON collector_dead_letter(task_name);
CREATE INDEX idx_collector_dead_letter_created_at ON collector_dead_letter(created_at DESC);

-- ============================================================
-- 10. LLM 配置域（后台管理）
-- ============================================================

CREATE TABLE llm_config (
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

CREATE INDEX idx_llm_configs_active ON llm_config(provider) WHERE is_active = TRUE;

CREATE UNIQUE INDEX idx_llm_config_default
    ON llm_config(is_default) WHERE is_default = TRUE;

-- ============================================================
-- 11. 采集渠道配置域（后台管理）
-- ============================================================

CREATE TABLE collector_channel_config (
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

CREATE INDEX idx_collector_channel_enabled ON collector_channel_config(is_enabled);
CREATE INDEX idx_collector_channel_supported_types ON collector_channel_config USING GIN(supported_data_types);

-- 渠道-数据类型关联及优先级（同 data_type 下 priority 越小越优先）
CREATE TABLE collector_channel_data_type (
    id          BIGSERIAL PRIMARY KEY,
    channel_id  BIGINT      NOT NULL REFERENCES collector_channel_config(id) ON DELETE CASCADE,
    data_type   VARCHAR(50) NOT NULL,
    priority    INTEGER     NOT NULL DEFAULT 100,
    CONSTRAINT uq_collector_channel_data_type_channel_data_type UNIQUE (channel_id, data_type)
);

CREATE INDEX idx_collector_channel_data_type_data_type_priority ON collector_channel_data_type(data_type, priority);

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

CREATE TABLE IF NOT EXISTS capital_fund_flow_sector (
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

    PRIMARY KEY (sector_code, sector_type, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_capital_fund_flow_sector_date ON capital_fund_flow_sector(trade_date DESC);

CREATE TABLE IF NOT EXISTS pool_dragon_tiger_stock (
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
CREATE INDEX IF NOT EXISTS idx_pool_dragon_tiger_stock_date ON pool_dragon_tiger_stock(trade_date DESC);

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

CREATE TABLE IF NOT EXISTS fund_holding (
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
CREATE INDEX IF NOT EXISTS idx_fund_holding_report_date ON fund_holding(report_date DESC);
CREATE INDEX IF NOT EXISTS idx_fund_holding_stock_code ON fund_holding(stock_code);

-- ============================================================
-- 14. 涨停股池（每日复盘：涨停板 / 连板天梯）
-- ============================================================

CREATE TABLE IF NOT EXISTS pool_limit_up_stock (
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
    broken_limit_count INT,
    limit_status         VARCHAR(20),
    consecutive_boards INT,
    industry           VARCHAR(100),
    source             VARCHAR(50),
    created_at         TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (trade_date, stock_code)
);
CREATE INDEX IF NOT EXISTS idx_pool_limit_up_stock_date ON pool_limit_up_stock(trade_date DESC);

-- ============================================================
-- 15. 市场涨跌统计（每日收盘快照：涨跌家数 / 涨跌停家数）
-- ============================================================

CREATE TABLE IF NOT EXISTS market_breadth (
    id              BIGSERIAL PRIMARY KEY,
    trade_date      DATE         NOT NULL,
    up_count        INT,
    down_count      INT,
    flat_count      INT,
    limit_up_count  INT,
    limit_down_count INT,
    broken_limit_count    INT,
    snapshot_time       VARCHAR(20),
    source          VARCHAR(50),
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (trade_date)
);

-- ============================================================
-- 16. 市场成交额（交易所官方每日成交额）
-- ============================================================

CREATE TABLE IF NOT EXISTS market_amount (
    id              BIGSERIAL PRIMARY KEY,
    trade_date      DATE         NOT NULL,
    amount          DECIMAL(20, 2),
    source          VARCHAR(50),
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (trade_date)
);

-- ============================================================
-- 17. 指数集合竞价成交额（9:25，单位：元）
-- ============================================================

CREATE TABLE IF NOT EXISTS quote_auction_index (
    id              BIGSERIAL PRIMARY KEY,
    trade_date      DATE         NOT NULL,
    index_code      VARCHAR(10)  NOT NULL,
    auction_amount  DECIMAL(20, 2) NOT NULL,
    source          VARCHAR(50),
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (trade_date, index_code)
);

CREATE INDEX IF NOT EXISTS idx_quote_auction_index_date ON quote_auction_index(trade_date DESC);

-- ============================================================
-- 18. 全球指标日行情（COMEX 黄金 / 美元指数 / 美债收益率等）
-- ============================================================

CREATE TABLE IF NOT EXISTS quote_global_index_daily (
    index_code    VARCHAR(16)   NOT NULL,
    trade_date    DATE          NOT NULL,
    open          DECIMAL(16,4),
    high          DECIMAL(16,4),
    low           DECIMAL(16,4),
    close         DECIMAL(16,4),
    change_pct    DECIMAL(12,4),
    volume        BIGINT,
    amount        DECIMAL(20,2),
    source        VARCHAR(50),
    created_at    TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (index_code, trade_date)
);

SELECT create_hypertable('quote_global_index_daily', 'trade_date', chunk_time_interval => INTERVAL '1 year', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_quote_global_index_daily_code_date
    ON quote_global_index_daily(index_code, trade_date DESC);

-- ============================================================
-- 19. 跟踪指数配置（工作台/行情卡展示清单，Admin CRUD 管理）
-- ============================================================

CREATE TABLE IF NOT EXISTS tracked_index_config (
    id               BIGSERIAL PRIMARY KEY,
    index_code       VARCHAR(16)  NOT NULL,
    index_name       VARCHAR(100) NOT NULL,
    market_category  VARCHAR(10)  NOT NULL CONSTRAINT chk_tracked_index_config_market_category
                     CHECK (market_category IN ('A股', '全球')),
    data_source      VARCHAR(50)  NOT NULL,
    sort_order       INT          NOT NULL DEFAULT 100,
    is_enabled       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_tracked_index_config_index_code UNIQUE (index_code)
);

-- ============================================================
-- 20. 投资日历事件（FOMC/BLS 官方日程等）
-- ============================================================

CREATE TABLE IF NOT EXISTS calendar_event (
    id              BIGSERIAL PRIMARY KEY,
    event_time      TIMESTAMPTZ  NOT NULL,
    end_time        TIMESTAMPTZ,
    title           VARCHAR(300) NOT NULL,
    category        VARCHAR(20)  NOT NULL CONSTRAINT chk_calendar_event_category
                    CHECK (category IN ('宏观', '央行动态', '新股', '解禁', '财报', '会议')),
    impact_markets  VARCHAR(50)[],
    source          VARCHAR(50),
    source_url      VARCHAR(1000),
    related_symbols TEXT[],
    source_hash     VARCHAR(32)  NOT NULL,          -- md5(source|event_time|title)，幂等键
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_calendar_event_source_hash UNIQUE (source_hash)
);

CREATE INDEX IF NOT EXISTS idx_calendar_event_time ON calendar_event(event_time);
CREATE INDEX IF NOT EXISTS idx_calendar_event_category_time ON calendar_event(category, event_time);

-- ============================================================
-- 21. 财联社电报（stream 驻留进程增量轮询，cls_msg_id 幂等）
-- ============================================================

CREATE TABLE IF NOT EXISTS news_telegraph (
    id            BIGSERIAL PRIMARY KEY,
    cls_msg_id    BIGINT       NOT NULL,
    title         VARCHAR(500),
    content       TEXT,
    category      VARCHAR(50),                       -- cls type 字段原值
    importance    SMALLINT,
    shared        SMALLINT,
    stock_codes   TEXT[],
    extra         JSONB,                             -- 其余 cls 字段（brief/shareurl 等）
    publish_time  TIMESTAMPTZ  NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_news_telegraph_cls_msg_id UNIQUE (cls_msg_id)
);

CREATE INDEX IF NOT EXISTS idx_news_telegraph_publish_time ON news_telegraph(publish_time DESC);
