-- ============================================================
-- AI Invest Assistant - PostgreSQL / TimescaleDB Schema
-- Version: 0.1.0
-- ============================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;      -- 知识库检索：halfvec 向量列（HNSW）
CREATE EXTENSION IF NOT EXISTS pg_trgm;     -- 知识库检索：词面三元组（GIN trgm）

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
-- 4. 资讯文档元数据域（doc_type 判别：news/announcement/research/financial_report）
-- ============================================================

CREATE TABLE news_document (
    id            BIGSERIAL PRIMARY KEY,
    stock_code    VARCHAR(10),
    doc_type      VARCHAR(20) NOT NULL CONSTRAINT chk_news_document_doc_type
                  CHECK (doc_type IN ('news', 'announcement', 'research', 'financial_report')),
    title         VARCHAR(500) NOT NULL,
    summary       TEXT,
    content       TEXT,
    source        VARCHAR(50),
    source_url    VARCHAR(1000),
    publish_date  TIMESTAMPTZ,
    sentiment     DECIMAL(5,2),              -- 情感得分 -1 ~ 1
    keywords      VARCHAR(100)[],
    industry_tags VARCHAR(50)[],
    created_at    TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_news_document_source_url UNIQUE (source_url)
);

CREATE INDEX idx_news_document_code_date ON news_document(stock_code, publish_date DESC);
CREATE INDEX idx_news_document_doc_type ON news_document(doc_type);
CREATE INDEX idx_news_document_publish_date ON news_document(publish_date DESC);

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
    content        TEXT,                      -- PDF 全文（pypdf 抽取，检索用）
    download_url   VARCHAR(1000),
    download_count INT DEFAULT 0,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_file_type ON file_metadata(file_type);
CREATE INDEX idx_file_stock_report ON file_metadata(stock_code, report_date);
CREATE INDEX idx_file_metadata_content_trgm ON file_metadata USING gin (content gin_trgm_ops);

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
    status        VARCHAR(16)  NOT NULL DEFAULT 'approved' CHECK (status IN ('pending', 'approved', 'rejected')),
    application_note TEXT,                                 -- 注册申请说明（pending 期间填写）
    reject_reason TEXT,                                    -- 驳回原因（rejected 时管理员填写）
    reviewed_by   BIGINT REFERENCES "user"(id),            -- 审批人
    reviewed_at   TIMESTAMPTZ,                             -- 审批时间
    settings      JSONB        DEFAULT '{}'::jsonb,
    last_login_at TIMESTAMPTZ,
    created_at    TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX idx_user_email ON "user"(email);
CREATE INDEX idx_user_status_pending ON "user"(status) WHERE status = 'pending';

CREATE TABLE user_watchlist_group (
    id                BIGSERIAL PRIMARY KEY,
    user_id           BIGINT       NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    name              VARCHAR(50)  NOT NULL,
    sort_order        INT          NOT NULL DEFAULT 0,
    is_default        BOOLEAN      NOT NULL DEFAULT FALSE,
    ai_review_enabled BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ  DEFAULT NOW(),

    UNIQUE (user_id, name)
);

CREATE INDEX idx_user_watchlist_group_user ON user_watchlist_group(user_id);

CREATE TABLE user_watchlist (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    stock_code VARCHAR(10) NOT NULL,
    tags       VARCHAR(50)[],
    group_id   BIGINT NOT NULL REFERENCES user_watchlist_group(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (user_id, stock_code)
);

CREATE INDEX idx_watchlist_user ON user_watchlist(user_id);
CREATE INDEX idx_user_watchlist_group_id ON user_watchlist(group_id);

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

CREATE INDEX idx_ai_skill_stock_status ON ai_analysis_result(skill_id, stock_code, status, created_at DESC);
CREATE INDEX idx_ai_skill_hash_status ON ai_analysis_result(skill_id, input_hash, status, created_at DESC);
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
    remark          VARCHAR(200),            -- 实例级用途备注（同 task_type 多实例时区分用途）
    schedule        VARCHAR(100),             -- cron 表达式或描述
    is_active       BOOLEAN      DEFAULT true,
    last_run_at     TIMESTAMPTZ,
    last_status     VARCHAR(20)  DEFAULT 'pending' CHECK (last_status IN ('pending', 'running', 'success', 'failed', 'skipped')),
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
    message     TEXT,
    metadata    JSONB,

    CONSTRAINT uq_collector_log_celery_task_id UNIQUE (celery_task_id)
);

CREATE INDEX idx_collector_log_started ON collector_log(started_at DESC);
CREATE INDEX idx_collector_log_celery_task_id ON collector_log(celery_task_id);
CREATE INDEX idx_collector_log_status_started_at ON collector_log(status, started_at DESC);
CREATE INDEX idx_collector_log_task_started ON collector_log(task_name, started_at DESC);

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
    protocol            VARCHAR(20)  NOT NULL DEFAULT 'openai',
    base_url            VARCHAR(500) NOT NULL,
    api_key_encrypted   TEXT         NOT NULL,
    model_name          VARCHAR(100) NOT NULL,
    is_default          BOOLEAN      NOT NULL DEFAULT FALSE,
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    extra               JSONB        NOT NULL DEFAULT '{}'::jsonb,
    purpose             VARCHAR(16)  NOT NULL DEFAULT 'chat',   -- 用途维度：chat / embedding / vision（F-KB 模型角色绑定）
    last_tested_at      TIMESTAMPTZ,
    last_test_status    VARCHAR(20),
    last_test_error     TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_llm_config_protocol CHECK (protocol IN ('openai', 'anthropic')),
    CONSTRAINT chk_llm_config_purpose CHECK (purpose IN ('chat', 'embedding', 'vision'))
);

CREATE INDEX idx_llm_configs_active ON llm_config(provider) WHERE is_active = TRUE;

CREATE UNIQUE INDEX idx_llm_config_default
    ON llm_config(is_default) WHERE is_default = TRUE;

-- ============================================================
-- 10a-2. MCP 服务配置（后台管理；工具注入 Phase 2 接入）
-- ============================================================

CREATE TABLE IF NOT EXISTS mcp_server_config (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    transport_type  VARCHAR(10)  NOT NULL DEFAULT 'http', -- stdio | http | sse
    command         VARCHAR(500),                -- stdio：可执行命令
    args            JSONB NOT NULL DEFAULT '[]', -- stdio：命令参数
    url             VARCHAR(500),                -- http/sse：端点
    env             JSONB NOT NULL DEFAULT '{}', -- stdio 环境变量（含密钥）
    headers         JSONB NOT NULL DEFAULT '{}', -- http/sse 认证头
    enabled         BOOLEAN NOT NULL DEFAULT FALSE,
    timeout_seconds INT NOT NULL DEFAULT 30,
    last_status     VARCHAR(20),                 -- ok | failed | untested
    last_error      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_mcp_server_config_name UNIQUE (name),
    CONSTRAINT chk_mcp_server_config_transport_type
        CHECK (transport_type IN ('stdio', 'http', 'sse'))
);

-- ============================================================
-- 10b. 代理服务器配置（后台管理，采集渠道按需绑定）
-- ============================================================

CREATE TABLE proxy_config (
    id                  BIGSERIAL PRIMARY KEY,
    name                VARCHAR(128) NOT NULL,
    protocol            VARCHAR(16)  NOT NULL DEFAULT 'http',
    host                VARCHAR(255) NOT NULL,
    port                INTEGER      NOT NULL,
    username            VARCHAR(255),
    password_encrypted  TEXT,
    is_enabled          BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_proxy_config_name UNIQUE (name),
    CONSTRAINT chk_proxy_config_protocol CHECK (protocol IN ('http', 'socks5')),
    CONSTRAINT chk_proxy_config_port CHECK (port > 0 AND port < 65536)
);

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
    proxy_config_id     BIGINT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT fk_collector_channel_config_proxy_config
        FOREIGN KEY (proxy_config_id) REFERENCES proxy_config(id) ON DELETE SET NULL
);

CREATE INDEX idx_collector_channel_enabled ON collector_channel_config(is_enabled);
CREATE INDEX idx_collector_channel_supported_types ON collector_channel_config USING GIN(supported_data_types);
CREATE INDEX idx_collector_channel_config_proxy_config_id ON collector_channel_config(proxy_config_id);

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

ALTER TABLE news_document
    ADD COLUMN IF NOT EXISTS extra JSONB DEFAULT '{}'::jsonb;

-- 扩展 doc_type 枚举以支持财报采集
DO $$
BEGIN
    ALTER TABLE news_document
        DROP CONSTRAINT IF EXISTS chk_news_document_doc_type;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_news_document_doc_type'
          AND conrelid = 'news_document'::regclass
    ) THEN
        ALTER TABLE news_document
            ADD CONSTRAINT chk_news_document_doc_type
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
-- 20. 投资日历事件（财联社投资日历/FOMC/BLS 官方日程等，news_ 家族）
-- ============================================================

CREATE TABLE IF NOT EXISTS news_calendar_event (
    id              BIGSERIAL PRIMARY KEY,
    event_time      TIMESTAMPTZ  NOT NULL,
    end_time        TIMESTAMPTZ,
    title           VARCHAR(300) NOT NULL,
    category        VARCHAR(20)  NOT NULL CONSTRAINT chk_news_calendar_event_category
                    CHECK (category IN ('宏观', '央行动态', '新股', '解禁', '财报', '会议')),
    impact_markets  VARCHAR(50)[],
    source          VARCHAR(50),
    source_url      VARCHAR(1000),
    related_symbols TEXT[],
    source_hash     VARCHAR(32)  NOT NULL,          -- md5(source|event_time|title)，幂等键
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_news_calendar_event_source_hash UNIQUE (source_hash)
);

CREATE INDEX IF NOT EXISTS idx_news_calendar_event_time ON news_calendar_event(event_time);
CREATE INDEX IF NOT EXISTS idx_news_calendar_event_category_time ON news_calendar_event(category, event_time);

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

-- ============================================================
-- 21b. 资讯 AI 重要度分级（跨源通用标注：电报/新闻/公告/推文/视频共用，
--      (source, item_id) 挂各源自有表业务主键，不改动源表）
-- ============================================================

CREATE TABLE IF NOT EXISTS news_ai_score (
    source       VARCHAR(32)  NOT NULL,
    item_id      VARCHAR(64)  NOT NULL,
    score        INT          NOT NULL,
    score_detail JSONB,
    scored_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    PRIMARY KEY (source, item_id),
    CONSTRAINT chk_news_ai_score_value CHECK (score >= 0 AND score <= 100)
);

CREATE INDEX IF NOT EXISTS idx_news_ai_score_score ON news_ai_score(score DESC);

-- ============================================================
-- 21c. 迭代 4 资讯 AI 增强：事件故事线（全局）/ 用户订阅命中 / 热点主题快照
-- ============================================================

CREATE TABLE IF NOT EXISTS news_storyline (
    id            BIGSERIAL PRIMARY KEY,
    title         VARCHAR(200) NOT NULL,
    summary       TEXT,
    status        VARCHAR(16) NOT NULL DEFAULT 'tracking' CONSTRAINT chk_news_storyline_status
                  CHECK (status IN ('tracking', 'near_end', 'finished')),
    origin        VARCHAR(8)  NOT NULL DEFAULT 'ai' CONSTRAINT chk_news_storyline_origin
                  CHECK (origin IN ('ai', 'manual')),
    user_id       BIGINT REFERENCES "user"(id) ON DELETE CASCADE,   -- 手动建线者（AI 线为 NULL）
    report_count  INT NOT NULL DEFAULT 0,
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_seen_at  TIMESTAMPTZ NOT NULL,
    latest_brief  TEXT,
    nodes         JSONB,                                -- 节点链 [{time, brief}]
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_news_storyline_status
    ON news_storyline(status, last_seen_at DESC);

CREATE TABLE IF NOT EXISTS user_news_storyline (
    user_id      BIGINT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    storyline_id BIGINT NOT NULL REFERENCES news_storyline(id) ON DELETE CASCADE,
    action       VARCHAR(8) NOT NULL DEFAULT 'active' CONSTRAINT chk_user_news_storyline_action
                 CHECK (action IN ('active', 'stopped')),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, storyline_id)
);

CREATE TABLE IF NOT EXISTS news_storyline_item (
    storyline_id BIGINT NOT NULL REFERENCES news_storyline(id) ON DELETE CASCADE,
    source       VARCHAR(32) NOT NULL,                  -- 与 news_ai_score.source 同口径
    item_id      VARCHAR(64) NOT NULL,                  -- 源表业务主键（电报=cls_msg_id）
    added_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (storyline_id, source, item_id),
    CONSTRAINT uq_news_storyline_item_item UNIQUE (source, item_id)
);

CREATE TABLE IF NOT EXISTS user_news_subscription (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    keyword      VARCHAR(100) NOT NULL,
    channels     JSONB,                                 -- 命中渠道过滤（NULL/空=全部渠道）
    push_enabled BOOLEAN NOT NULL DEFAULT FALSE,        -- 推送通道实装前仅存配置
    enabled      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_news_subscription_user_keyword UNIQUE (user_id, keyword)
);

CREATE TABLE IF NOT EXISTS news_subscription_hit (
    subscription_id BIGINT NOT NULL REFERENCES user_news_subscription(id) ON DELETE CASCADE,
    source          VARCHAR(32) NOT NULL,
    item_id         VARCHAR(64) NOT NULL,
    hit_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (subscription_id, source, item_id)
);

CREATE INDEX IF NOT EXISTS idx_news_subscription_hit_item
    ON news_subscription_hit(source, item_id);

CREATE TABLE IF NOT EXISTS news_topic_snapshot (
    trade_date   DATE NOT NULL,
    session      VARCHAR(8) NOT NULL CONSTRAINT chk_news_topic_snapshot_session
                 CHECK (session IN ('intraday', 'post')),
    topics       JSONB,                                 -- [{title, sentiment, votes, item_ids, chain, heat, factors, asOfTradeDate}]
    wordcloud    JSONB,                                 -- [{word, count}]
    input_hash   VARCHAR(64),
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (trade_date, session)
);

-- ============================================================
-- 22. Skill 注册表（builtin 登记 + custom 定义；builtin 行由应用启动
--     sync_builtin_skills 幂等同步写入，无静态 seed）
-- ============================================================

CREATE TABLE IF NOT EXISTS skill (
    id                BIGSERIAL PRIMARY KEY,
    skill_id          VARCHAR(100) NOT NULL,
    label             VARCHAR(100) NOT NULL,
    kind              VARCHAR(20)  NOT NULL CONSTRAINT chk_skill_kind
                      CHECK (kind IN ('executable', 'prompt_only', 'doc_only', 'custom')),
    scenario          VARCHAR(20)  CONSTRAINT chk_skill_scenario
                      CHECK (scenario IN ('market', 'stock', 'chain', 'report', 'news', 'custom')),
    description       TEXT,
    is_builtin        BOOLEAN NOT NULL DEFAULT TRUE,
    owner_user_id     BIGINT REFERENCES "user"(id) ON DELETE CASCADE,
    published         BOOLEAN NOT NULL DEFAULT FALSE,
    sort              INT NOT NULL DEFAULT 100,
    custom_definition JSONB,                             -- custom 专用：{skill_md, system_prompt, user_prompt_template?, sections?[]}
    version           INT NOT NULL DEFAULT 1,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_skill_skill_id UNIQUE (skill_id)
);

CREATE INDEX IF NOT EXISTS idx_skill_owner ON skill(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_skill_published_sort ON skill(published, sort);

CREATE TABLE IF NOT EXISTS user_skill (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    skill_id     VARCHAR(100) NOT NULL REFERENCES skill(skill_id) ON DELETE CASCADE,
    enabled      BOOLEAN NOT NULL DEFAULT TRUE,
    sort         INT NOT NULL DEFAULT 100,
    installed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_user_skill_user_skill UNIQUE (user_id, skill_id)
);

CREATE INDEX IF NOT EXISTS idx_user_skill_user ON user_skill(user_id);
CREATE INDEX IF NOT EXISTS idx_user_skill_skill ON user_skill(skill_id);

-- ============================================================
-- 23. 迭代 2 监测分组数据：FedWatch 概率快照 / 板块收盘快照
-- ============================================================

CREATE TABLE IF NOT EXISTS fed_watch_snapshot (
    as_of_date         DATE     NOT NULL,               -- CT 数据日期
    data_as_at         TIMESTAMPTZ NOT NULL,            -- 官网 "Data as of" CT 时刻（aware UTC）
    current_range_low  INT      NOT NULL,               -- 当前目标区间下限（bps）
    current_range_high INT      NOT NULL,               -- 当前目标区间上限（bps）

    PRIMARY KEY (as_of_date),
    CONSTRAINT chk_fed_watch_snapshot_range CHECK (current_range_low < current_range_high)
);

CREATE TABLE IF NOT EXISTS fed_watch_probability (
    as_of_date   DATE         NOT NULL,
    meeting_date DATE         NOT NULL,
    range_low    INT          NOT NULL,
    range_high   INT          NOT NULL,
    probability  DECIMAL(6,3) NOT NULL,                 -- 0-100
    created_at   TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (as_of_date, meeting_date, range_low),
    CONSTRAINT chk_fed_watch_probability_value CHECK (probability >= 0 AND probability <= 100),
    CONSTRAINT chk_fed_watch_probability_range CHECK (range_low < range_high)
);

SELECT create_hypertable('fed_watch_probability', 'as_of_date', chunk_time_interval => INTERVAL '1 year', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS quote_sector_daily (
    sector_type       VARCHAR(16)  NOT NULL CONSTRAINT chk_quote_sector_daily_type
                      CHECK (sector_type IN ('industry', 'concept')),
    sector_code       VARCHAR(16)  NOT NULL,            -- 东财板块代码（BKxxxx）
    sector_name       VARCHAR(50)  NOT NULL,
    trade_date        DATE         NOT NULL,
    close             DECIMAL(16,4),
    change_pct        DECIMAL(12,4),
    amount            DECIMAL(20,2),                    -- 成交额（元）
    turnover_rate     DECIMAL(10,4),                    -- 换手率（%）
    up_count          INT,
    down_count        INT,
    leader_stock_name VARCHAR(50),
    source            VARCHAR(50),
    created_at        TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (sector_type, sector_code, trade_date)
);

SELECT create_hypertable('quote_sector_daily', 'trade_date', chunk_time_interval => INTERVAL '1 year', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_quote_sector_daily_type_date
    ON quote_sector_daily(sector_type, trade_date DESC);

-- 板块指数日 K（同花顺渠道，板块详情页真实 K 线；经板块名与东财体系桥接）
CREATE TABLE IF NOT EXISTS quote_kline_sector_daily (
    sector_code VARCHAR(16)  NOT NULL,               -- 同花顺板块代码（881xxx）
    trade_date  DATE         NOT NULL,
    sector_type VARCHAR(16)  NOT NULL CONSTRAINT chk_quote_kline_sector_daily_type
                CHECK (sector_type IN ('industry', 'concept')),
    sector_name VARCHAR(50)  NOT NULL,               -- 桥接键：与东财板块同名
    open        DECIMAL(18, 4),
    high        DECIMAL(18, 4),
    low         DECIMAL(18, 4),
    close       DECIMAL(18, 4) NOT NULL,
    volume      BIGINT,                              -- 成交量（手）
    amount      DECIMAL(20, 2),                      -- 成交额（元）
    source      VARCHAR(20) NOT NULL DEFAULT 'ths',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT pk_quote_kline_sector_daily PRIMARY KEY (sector_code, trade_date)
);

SELECT create_hypertable('quote_kline_sector_daily', 'trade_date', chunk_time_interval => INTERVAL '1 year', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_quote_kline_sector_daily_name_date
    ON quote_kline_sector_daily(sector_name, trade_date DESC);

-- ============================================================
-- 24. 异动分析（板块 / 个股异动日表，规则检测 + top-N LLM 归因）
-- ============================================================

CREATE TABLE IF NOT EXISTS market_anomaly_sector (
    id                   BIGSERIAL PRIMARY KEY,
    trade_date           DATE        NOT NULL,
    sector_type          VARCHAR(10) NOT NULL CONSTRAINT chk_market_anomaly_sector_type
                         CHECK (sector_type IN ('industry', 'concept')),
    sector_code          VARCHAR(16) NOT NULL,
    sector_name          VARCHAR(50) NOT NULL,
    change_pct           NUMERIC(8, 4),                -- 当日涨跌幅 %
    amount               NUMERIC(20, 2),               -- 当日成交额（元）
    amount_ratio         NUMERIC(8, 2),                -- 当日额 / 5 日均额
    up_count             INT,
    down_count           INT,
    trend_facts          JSONB,                        -- 趋势事实（通道/量能/拐点，trend_facts 模块产出）
    anomaly_types        JSONB       NOT NULL DEFAULT '[]',  -- 命中维度列表
    strength             INT         NOT NULL,          -- 强度 0-100
    attribution_category VARCHAR(20),                  -- resonance / rotation（归因后回填，可空）
    attribution_summary  TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_market_anomaly_sector UNIQUE (trade_date, sector_type, sector_code)
);

CREATE INDEX IF NOT EXISTS idx_market_anomaly_sector_date
    ON market_anomaly_sector(trade_date DESC);

CREATE TABLE IF NOT EXISTS market_anomaly_stock (
    id                   BIGSERIAL PRIMARY KEY,
    trade_date           DATE        NOT NULL,
    stock_code           VARCHAR(10) NOT NULL,
    stock_name           VARCHAR(50) NOT NULL,
    close                NUMERIC(12, 4),
    change_pct           NUMERIC(8, 4),                -- 当日涨跌幅 %
    turnover_rate        NUMERIC(8, 4),                -- 换手率 %
    volume_ratio         NUMERIC(8, 2),                -- 当日量 / 5 日均量
    ma60                 NUMERIC(12, 4),               -- 当日 MA60 值
    is_above_ma60        BOOLEAN     NOT NULL DEFAULT FALSE,
    ma60_breakout        BOOLEAN     NOT NULL DEFAULT FALSE,  -- 存量 wire 字段（展示兼容，不再计分）
    trend_facts          JSONB,                        -- 趋势事实（通道/量能/三类拐点，trend_facts 模块产出）
    anomaly_types        JSONB       NOT NULL DEFAULT '[]',
    strength             INT         NOT NULL,
    attribution_category VARCHAR(20),                  -- breakout / acceleration / pullback（可空）
    attribution_summary  TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_market_anomaly_stock UNIQUE (trade_date, stock_code)
);

CREATE INDEX IF NOT EXISTS idx_market_anomaly_stock_date
    ON market_anomaly_stock(trade_date DESC);

-- ============================================================
-- collector_health_status：采集健康快照（collector_health_check 定时任务
-- upsert；页面只读快照）
-- ============================================================

CREATE TABLE IF NOT EXISTS collector_health_status (
    id                      BIGSERIAL PRIMARY KEY,
    task_type               VARCHAR(64) NOT NULL,          -- TASK_SPECS 键
    source                  VARCHAR(50) NOT NULL,          -- 渠道标识
    status                  VARCHAR(16) NOT NULL,          -- healthy/degraded/critical/silent/paused/unconfigured
    role                    VARCHAR(8)  NOT NULL,          -- primary/backup/single
    domain                  VARCHAR(16) NOT NULL,          -- 数据域（TASK_TYPE_DOMAIN）
    success_rate_24h        NUMERIC(6, 5),                 -- skipped 剔除口径
    success_rate_7d         NUMERIC(6, 5),
    consecutive_failures    INT         NOT NULL DEFAULT 0,
    last_success_at         TIMESTAMPTZ,
    windows_without_success INT         NOT NULL DEFAULT 0, -- 应成功而未成功的计划窗口数
    last_error_summary      VARCHAR(500),
    last_error_cause        VARCHAR(16),                   -- 错误归因分类
    reasons                 JSONB        NOT NULL DEFAULT '[]'::jsonb, -- 判定依据（why，按序）
    is_high_frequency       BOOLEAN     NOT NULL DEFAULT FALSE, -- 单日场次>=48
    last_records_count      INT,                           -- 最近一次入库量
    last_records_date       DATE,
    state_changed_at        TIMESTAMPTZ NOT NULL,          -- 状态翻转时间
    checked_at              TIMESTAMPTZ NOT NULL,          -- 本次检测时间（同批次同值）

    CONSTRAINT uq_collector_health_status UNIQUE (task_type, source),
    CONSTRAINT chk_collector_health_status_status CHECK (status IN
        ('healthy', 'degraded', 'critical', 'silent', 'paused', 'unconfigured')),
    CONSTRAINT chk_collector_health_status_role CHECK (role IN ('primary', 'backup', 'single'))
);

CREATE INDEX IF NOT EXISTS idx_collector_health_status_status
    ON collector_health_status(status);

-- ============================================================
-- user_kline_drawing / ai_kline_drawing：K 线画线（F-DRAW，
-- 用户画线 per-user 私有每行一条；AI 画线全局共享每标的每周期一套）
-- ============================================================

CREATE TABLE IF NOT EXISTS user_kline_drawing (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT      NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    target_type  VARCHAR(16) NOT NULL,                 -- stock / index / sector
    target_code  VARCHAR(16) NOT NULL,                 -- 6 位代码或指数/板块代码
    period       VARCHAR(8)  NOT NULL,                 -- daily / weekly / monthly
    drawing_type VARCHAR(16) NOT NULL,                 -- trendline / ray / hline / box / text
    payload      JSONB       NOT NULL,                 -- {anchors[], direction?, text?, style{}}
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_user_kline_drawing_target_type CHECK (target_type IN ('stock', 'index', 'sector')),
    CONSTRAINT chk_user_kline_drawing_period CHECK (period IN ('daily', 'weekly', 'monthly')),
    CONSTRAINT chk_user_kline_drawing_type CHECK (drawing_type IN ('trendline', 'ray', 'hline', 'box', 'text'))
);

CREATE INDEX IF NOT EXISTS idx_user_kline_drawing_scope
    ON user_kline_drawing(user_id, target_type, target_code, period);

CREATE TABLE IF NOT EXISTS ai_kline_drawing (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT      NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,  -- 多租户：AI 画线为 per-user 私有工作区
    target_type VARCHAR(16) NOT NULL,
    target_code VARCHAR(16) NOT NULL,
    period      VARCHAR(8)  NOT NULL,
    skill_id    VARCHAR(64) NOT NULL,                  -- 最近一次生成来源（kline-smart-drawing）
    trade_date  DATE,                                  -- 最近一次生成对应交易日（展示用）
    drawings    JSONB       NOT NULL DEFAULT '[]'::jsonb, -- [{drawingType, anchors, direction?, label, reason}]
    summary     TEXT,                                  -- 本组画线一段话说明（面板展示）
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_ai_kline_drawing UNIQUE (user_id, target_type, target_code, period),
    CONSTRAINT chk_ai_kline_drawing_target_type CHECK (target_type IN ('stock', 'index', 'sector')),
    CONSTRAINT chk_ai_kline_drawing_period CHECK (period IN ('daily', 'weekly', 'monthly'))
);

CREATE INDEX IF NOT EXISTS idx_ai_kline_drawing_scope
    ON ai_kline_drawing(user_id, target_type, target_code, period);

-- ============================================================
-- 账号准入与 AI 用量治理（F-ACCT，arch/10）
-- ============================================================

CREATE TABLE IF NOT EXISTS user_ai_quota (
    user_id      BIGINT PRIMARY KEY REFERENCES "user"(id) ON DELETE CASCADE,
    total_tokens BIGINT,                                  -- NULL = 不设上限（豁免）
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by   BIGINT REFERENCES "user"(id)
);

CREATE TABLE IF NOT EXISTS user_token_usage (
    id                BIGSERIAL PRIMARY KEY,
    user_id           BIGINT REFERENCES "user"(id) ON DELETE SET NULL,  -- 系统维度为 NULL
    feature           VARCHAR(20) NOT NULL,               -- assistant / page / api_key / system / kb_clean / kb_extract / kb_vision / kb_embed
    model_name        VARCHAR(100) NOT NULL,
    provider          VARCHAR(50)  NOT NULL,              -- 渠道 provider 或 'byok'
    outlet            VARCHAR(10)  NOT NULL,              -- system / byok
    prompt_tokens     INT NOT NULL,
    completion_tokens INT NOT NULL,
    total_tokens      INT NOT NULL,
    estimated         BOOLEAN NOT NULL DEFAULT FALSE,
    detail            JSONB,                              -- F-KB 建库上下文：{sourceId, mediaId, taskRunId}
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_user_token_usage_feature CHECK (feature IN
        ('assistant', 'page', 'api_key', 'system', 'kb_clean', 'kb_extract', 'kb_vision', 'kb_embed')),
    CONSTRAINT chk_user_token_usage_outlet CHECK (outlet IN ('system', 'byok'))
);

CREATE INDEX IF NOT EXISTS idx_user_token_usage_user_time ON user_token_usage(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_token_usage_time ON user_token_usage(created_at);
CREATE INDEX IF NOT EXISTS idx_user_token_usage_feature_time ON user_token_usage(feature, created_at);

CREATE TABLE IF NOT EXISTS user_llm_config (
    id                BIGSERIAL PRIMARY KEY,
    user_id           BIGINT NOT NULL UNIQUE REFERENCES "user"(id) ON DELETE CASCADE,
    protocol          VARCHAR(20) NOT NULL,
    base_url          VARCHAR(255) NOT NULL,
    model_name        VARCHAR(100) NOT NULL,
    api_key_encrypted TEXT NOT NULL,                      -- Fernet 认证加密（app/utils/crypto.py）
    api_key_masked    VARCHAR(32)  NOT NULL,              -- 冗余脱敏串，读路径免解密
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_user_llm_config_protocol CHECK (protocol IN ('openai', 'anthropic'))
);

CREATE TABLE IF NOT EXISTS admin_audit_log (
    id             BIGSERIAL PRIMARY KEY,
    actor_id       BIGINT NOT NULL REFERENCES "user"(id),
    action         VARCHAR(50) NOT NULL,                  -- register.approve / register.reject / quota.adjust / account_setting.update
    target_user_id BIGINT REFERENCES "user"(id) ON DELETE SET NULL,
    detail         JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip             VARCHAR(45),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_admin_audit_log_actor_time ON admin_audit_log(actor_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_action_time ON admin_audit_log(action, created_at DESC);

CREATE TABLE IF NOT EXISTS system_setting (
    key        VARCHAR(50) PRIMARY KEY,                   -- account.default_quota_tokens / account.pending_expire_days / quota.admin_exempt
    value      JSONB NOT NULL,
    updated_by BIGINT REFERENCES "user"(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 全局设置缺省行（管理端可改）
INSERT INTO system_setting (key, value) VALUES
    ('account.default_quota_tokens', '100000'),
    ('account.pending_expire_days', '30'),
    ('quota.admin_exempt', 'true')
ON CONFLICT (key) DO NOTHING;

-- ============================================================
-- F-SOC 社媒大 V 情绪追踪（迭代 11）
-- ============================================================

CREATE TABLE IF NOT EXISTS social_account (
    id                    BIGSERIAL PRIMARY KEY,
    platform              VARCHAR(16)  NOT NULL,
    sec_uid               VARCHAR(128) NOT NULL,                   -- 平台内唯一标识（抖音 sec_user_id，新账号可超 64 字符）
    alias                 VARCHAR(64)  NOT NULL,                   -- 展示别名
    category              VARCHAR(32)  NOT NULL DEFAULT 'finance_kol',  -- macro_policy / finance_kol / industry
    remark                VARCHAR(500),
    poll_interval_minutes INT          NOT NULL DEFAULT 60,
    is_active             BOOLEAN      NOT NULL DEFAULT true,
    last_collected_at     TIMESTAMPTZ,
    last_post_at          TIMESTAMPTZ,
    last_error            VARCHAR(1000),                            -- 渠道侧账号失效诊断提示，不阻断采集
    last_error_at         TIMESTAMPTZ,
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_social_account_platform_sec_uid UNIQUE (platform, sec_uid),
    CONSTRAINT chk_social_account_platform CHECK (platform IN ('douyin')),
    CONSTRAINT chk_social_account_poll_interval CHECK (poll_interval_minutes >= 5)
);

CREATE INDEX IF NOT EXISTS idx_social_account_active ON social_account(is_active);

CREATE TABLE IF NOT EXISTS social_post (
    id                BIGSERIAL PRIMARY KEY,
    account_id        BIGINT       NOT NULL REFERENCES social_account(id) ON DELETE CASCADE,
    platform          VARCHAR(16)  NOT NULL,
    video_id          VARCHAR(64)  NOT NULL,                       -- 平台内容唯一 ID（aweme_id）
    title             VARCHAR(500),
    caption           TEXT,                                        -- 完整文案（desc）
    topic_tags        JSONB        NOT NULL DEFAULT '[]'::jsonb,   -- 话题标签（去 #）
    cover_url         TEXT,
    duration_seconds  INT,
    published_at      TIMESTAMPTZ  NOT NULL,                       -- 发布时刻（aware UTC）
    digg_count        BIGINT,
    comment_count     BIGINT,
    share_count       BIGINT,
    transcript_status VARCHAR(16)  NOT NULL DEFAULT 'ok',          -- 两阶段落库：listing 落 pending，逐条转写回写 ok/降级 missing
    transcript_text   TEXT,                                        -- 临时文稿缓存，判后即清，任何 API 永不透出
    transcript_meta   JSONB,                                       -- ASR 用量对账：音频时长/字符数/provider
    judged_at         TIMESTAMPTZ,                                 -- NULL=待判（判断幂等键）
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_social_post_platform_video UNIQUE (platform, video_id),
    CONSTRAINT chk_social_post_transcript_status CHECK (transcript_status IN ('ok', 'missing', 'pending'))
);

CREATE INDEX IF NOT EXISTS idx_social_post_published ON social_post(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_social_post_account_published ON social_post(account_id, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_social_post_pending ON social_post(judged_at) WHERE judged_at IS NULL;

CREATE TABLE IF NOT EXISTS social_sentiment (
    id             BIGSERIAL PRIMARY KEY,
    post_id        BIGINT       NOT NULL REFERENCES social_post(id) ON DELETE CASCADE,
    is_relevant    BOOLEAN      NOT NULL,                         -- 无关内容（生活/广告）不入视图
    stance         VARCHAR(16)  NOT NULL,
    confidence     REAL         NOT NULL,
    core_arguments JSONB        NOT NULL DEFAULT '[]'::jsonb,      -- 一句话论点数组
    targets        JSONB        NOT NULL DEFAULT '[]'::jsonb,      -- [{target_type, name, code?}]
    summary        VARCHAR(1000) NOT NULL,
    model_name     VARCHAR(100) NOT NULL,                          -- 判断对账/审计
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_social_sentiment_post UNIQUE (post_id),
    CONSTRAINT chk_social_sentiment_stance CHECK (stance IN ('bullish', 'bearish', 'neutral')),
    CONSTRAINT chk_social_sentiment_confidence CHECK (confidence >= 0 AND confidence <= 1)
);

CREATE INDEX IF NOT EXISTS idx_social_sentiment_created ON social_sentiment(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_social_sentiment_stance_created ON social_sentiment(stance, created_at DESC);

-- ASR 转写服务渠道配置（单行表；04 知识库后置排期时直接复用同一设施）
CREATE TABLE IF NOT EXISTS asr_channel_config (
    id                BIGSERIAL PRIMARY KEY CHECK (id = 1),
    provider          VARCHAR(32)  NOT NULL DEFAULT 'minimax',
    base_url          VARCHAR(200) NOT NULL DEFAULT 'https://api.minimaxi.com',
    model             VARCHAR(64)  NOT NULL DEFAULT 'asr-1.0',
    api_key_encrypted TEXT,                                        -- Fernet 认证加密
    api_key_masked    VARCHAR(64),                                 -- 冗余脱敏串
    extra             JSONB        NOT NULL DEFAULT '{}'::jsonb,   -- 协议附加参数（timestamp_level/stream）
    hotwords          JSONB        NOT NULL DEFAULT '[]'::jsonb,   -- 财经热词表（注入判断 prompt）
    max_audio_seconds INT          NOT NULL DEFAULT 600,           -- 单条音频时长上限截断
    enabled           BOOLEAN      NOT NULL DEFAULT false,
    updated_by        BIGINT REFERENCES "user"(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- 缺省配置行（管理端「ASR 配置」维护；enabled 默认关，配好密钥再开）
INSERT INTO asr_channel_config (id, provider, base_url, model)
VALUES (1, 'minimax', 'https://api.minimaxi.com', 'asr-1.0')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- F-KB 温成趋势理论知识库（kb_source / kb_media / kb_transcript_segment /
-- kb_knowledge_point / kb_image_asset / kb_settings；arch/12）
-- ============================================================

CREATE TABLE IF NOT EXISTS kb_source (
    id                    BIGSERIAL PRIMARY KEY,
    source_type           VARCHAR(16)  NOT NULL,                     -- course / book
    name                  VARCHAR(200) NOT NULL,
    author                VARCHAR(100),                              -- 讲师 / 作者
    description           TEXT,
    enabled               BOOLEAN      NOT NULL DEFAULT TRUE,
    chapter_tree          JSONB        NOT NULL DEFAULT '{"draft": null, "published": null}'::jsonb,
    storage_bytes         BIGINT       NOT NULL DEFAULT 0,           -- COS 登记字节数聚合
    pending_cleanup_bytes BIGINT       NOT NULL DEFAULT 0,           -- 异步清理未完成量
    deleted_at            TIMESTAMPTZ,                               -- 软删（24h 恢复窗）
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_kb_source_type CHECK (source_type IN ('course', 'book'))
);

CREATE INDEX IF NOT EXISTS idx_kb_source_active ON kb_source(deleted_at) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS kb_media (
    id               BIGSERIAL PRIMARY KEY,
    source_id        BIGINT       NOT NULL REFERENCES kb_source(id) ON DELETE CASCADE,
    media_kind       VARCHAR(8)   NOT NULL,                          -- video / audio / book
    episode_no       INT,                                            -- 课程集号（书为 NULL）
    title            VARCHAR(300) NOT NULL,
    file_name        VARCHAR(500) NOT NULL,
    relative_path    VARCHAR(500),                                   -- 上传时的相对路径（目录结构展示）
    cos_key          VARCHAR(500) NOT NULL,
    file_size        BIGINT       NOT NULL DEFAULT 0,
    file_hash        VARCHAR(64)  NOT NULL,                          -- md5（uploaded 核对与去重）
    duration_seconds INT,                                            -- 课程素材时长（秒）
    page_count       INT,                                            -- 书册页数
    process_status   VARCHAR(16)  NOT NULL DEFAULT 'uploaded',
    process_error    VARCHAR(1000),
    process_meta     JSONB        NOT NULL DEFAULT '{}'::jsonb,      -- 用量对账：provider/model/audio_seconds/est_cost…
    extracted_at     TIMESTAMPTZ,                                    -- 知识抽取完成时刻（抽取任务幂等键）
    edited_at        TIMESTAMPTZ,                                    -- 文稿人工编辑时刻（脏传播源）
    vision_at        TIMESTAMPTZ,                                    -- 课程视频关键帧选帧完成时刻（视觉通道幂等键）
    deleted_at       TIMESTAMPTZ,                                    -- 软删（与 kb_source 同路径，24h 恢复窗）
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_kb_media_kind CHECK (media_kind IN ('video', 'audio', 'book')),
    CONSTRAINT chk_kb_media_status CHECK (process_status IN
        ('uploaded', 'awaiting_cost', 'queued', 'processing', 'done', 'failed'))
);

-- 集号唯一仅约束课程（书的 episode_no 为 NULL，PG 唯一约束不冲突多个 NULL）
CREATE UNIQUE INDEX IF NOT EXISTS uq_kb_media_source_episode
    ON kb_media(source_id, episode_no) WHERE episode_no IS NOT NULL;
-- 哈希去重仅约束存活行（软删行不占哈希位，24h 恢复窗内同内容可重传）
CREATE UNIQUE INDEX IF NOT EXISTS uq_kb_media_source_hash
    ON kb_media(source_id, file_hash) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_kb_media_source_status ON kb_media(source_id, process_status);
CREATE INDEX IF NOT EXISTS idx_kb_media_deleted ON kb_media(deleted_at) WHERE deleted_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS kb_transcript_segment (
    id              BIGSERIAL PRIMARY KEY,
    media_id        BIGINT      NOT NULL REFERENCES kb_media(id) ON DELETE CASCADE,
    source_id       BIGINT      NOT NULL REFERENCES kb_source(id) ON DELETE CASCADE,  -- 冗余，脏扫描按源过滤
    seq_no          INT         NOT NULL,
    text            TEXT        NOT NULL,
    start_ms        BIGINT,                                               -- 课程：句级起（毫秒）
    end_ms          BIGINT,
    page_start      INT,                                                  -- 书：页区间
    page_end        INT,
    embedding       halfvec(2048),                                        -- 向量检索列（物化任务写入）
    embedding_dirty BOOLEAN     NOT NULL DEFAULT TRUE,                    -- 物化任务增量拾取
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_kb_segment_media_seq UNIQUE (media_id, seq_no)
);

CREATE INDEX IF NOT EXISTS idx_kb_segment_dirty ON kb_transcript_segment(embedding_dirty) WHERE embedding_dirty;
CREATE INDEX IF NOT EXISTS idx_kb_segment_source_dirty ON kb_transcript_segment(source_id, embedding_dirty);
CREATE INDEX IF NOT EXISTS idx_kb_segment_embedding ON kb_transcript_segment USING hnsw (embedding halfvec_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_kb_segment_text_trgm ON kb_transcript_segment USING gin (text gin_trgm_ops);

CREATE TABLE IF NOT EXISTS kb_knowledge_point (
    id               BIGSERIAL PRIMARY KEY,
    source_id        BIGINT       NOT NULL REFERENCES kb_source(id) ON DELETE CASCADE,
    media_id         BIGINT       NOT NULL REFERENCES kb_media(id) ON DELETE CASCADE,
    point_type       VARCHAR(16)  NOT NULL,                         -- concept/theorem/method/discipline/case
    title            VARCHAR(300) NOT NULL,
    body             TEXT         NOT NULL,                         -- 正文（保留讲师表述）
    term_definition  TEXT,
    applicable_scene TEXT,
    excerpt          TEXT         NOT NULL,                         -- 原文摘录（审核后不可改）
    start_ms         BIGINT,                                        -- 课程定位（句级起止）
    end_ms           BIGINT,
    page_start       INT,                                           -- 书定位（页区间）
    page_end         INT,
    related_ids      JSONB        NOT NULL DEFAULT '[]'::jsonb,     -- 关联知识点 id
    chapter_path     JSONB        NOT NULL DEFAULT '[]'::jsonb,     -- 发布树节点 id 串
    status           VARCHAR(16)  NOT NULL DEFAULT 'draft',
    needs_review     BOOLEAN      NOT NULL DEFAULT FALSE,           -- excerpt 校验未过显式标记
    review_note      VARCHAR(1000),
    reviewed_by      BIGINT REFERENCES "user"(id) ON DELETE SET NULL,
    reviewed_at      TIMESTAMPTZ,
    search_text      TEXT GENERATED ALWAYS AS (                         -- 词面检索列 = 嵌入输入口径
        -- 生成列只能用不可变函数（concat_ws 为 STABLE）：CASE/COALESCE/|| 拼接，
        -- 非空段以 \n 连接、空/NULL 段跳过，与 Python join 口径逐点一致
        COALESCE(nullif(title, ''), '')
        || CASE WHEN nullif(title, '') IS NOT NULL AND nullif(term_definition, '') IS NOT NULL
                THEN E'\n' ELSE '' END || COALESCE(nullif(term_definition, ''), '')
        || CASE WHEN (nullif(title, '') IS NOT NULL OR nullif(term_definition, '') IS NOT NULL)
                   AND nullif(body, '') IS NOT NULL
                THEN E'\n' ELSE '' END || COALESCE(nullif(body, ''), '')
        || CASE WHEN (nullif(title, '') IS NOT NULL OR nullif(term_definition, '') IS NOT NULL
                      OR nullif(body, '') IS NOT NULL) AND nullif(applicable_scene, '') IS NOT NULL
                THEN E'\n' ELSE '' END || COALESCE(nullif(applicable_scene, ''), '')) STORED,
    embedding        halfvec(2048),                                     -- 向量检索列（物化任务写入）
    embedding_dirty  BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_kb_point_type CHECK (point_type IN ('concept', 'theorem', 'method', 'discipline', 'case')),
    CONSTRAINT chk_kb_point_status CHECK (status IN ('draft', 'published', 'rejected'))
);

CREATE INDEX IF NOT EXISTS idx_kb_point_source_status ON kb_knowledge_point(source_id, status);
CREATE INDEX IF NOT EXISTS idx_kb_point_dirty ON kb_knowledge_point(embedding_dirty) WHERE embedding_dirty;
CREATE INDEX IF NOT EXISTS idx_kb_point_chapter_path ON kb_knowledge_point USING GIN (chapter_path jsonb_path_ops);
CREATE INDEX IF NOT EXISTS idx_kb_point_embedding ON kb_knowledge_point USING hnsw (embedding halfvec_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_kb_point_search_text_trgm ON kb_knowledge_point USING gin (search_text gin_trgm_ops);

CREATE TABLE IF NOT EXISTS kb_image_asset (
    id                 BIGSERIAL PRIMARY KEY,
    media_id           BIGINT       NOT NULL REFERENCES kb_media(id) ON DELETE CASCADE,
    source_id          BIGINT       NOT NULL REFERENCES kb_source(id) ON DELETE CASCADE,
    page_no            INT,                                          -- 书页码（关键帧行为空）
    start_ms           BIGINT,                                       -- 课程关键帧起（毫秒）
    end_ms             BIGINT,
    bbox               JSONB,                                        -- 页内位置（可空）
    cos_key            VARCHAR(500) NOT NULL,                        -- 原图
    thumb_cos_key      VARCHAR(500),                                 -- 缩略图
    text_in_image      TEXT,                                         -- 图内文字（VLM 识别）
    caption            TEXT,                                         -- 图注推断
    vision_description TEXT,                                         -- 视觉描述
    describe_status    VARCHAR(16)  NOT NULL DEFAULT 'pending',
    describe_attempts  INT          NOT NULL DEFAULT 0,              -- 描述失败退避（≥3 终态 failed）
    search_text        TEXT GENERATED ALWAYS AS (                    -- 词面检索列 = 嵌入输入口径（三文本合并）
        -- 同 kb_knowledge_point.search_text：不可变拼接，空/NULL 段跳过
        COALESCE(nullif(text_in_image, ''), '')
        || CASE WHEN nullif(text_in_image, '') IS NOT NULL AND nullif(caption, '') IS NOT NULL
                THEN E'\n' ELSE '' END || COALESCE(nullif(caption, ''), '')
        || CASE WHEN (nullif(text_in_image, '') IS NOT NULL OR nullif(caption, '') IS NOT NULL)
                   AND nullif(vision_description, '') IS NOT NULL
                THEN E'\n' ELSE '' END || COALESCE(nullif(vision_description, ''), '')) STORED,
    embedding          halfvec(2048),                                -- 向量检索列（物化任务写入）
    embedding_dirty    BOOLEAN      NOT NULL DEFAULT TRUE,
    index_excluded     BOOLEAN      NOT NULL DEFAULT FALSE,          -- 人工排除：不进检索索引
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_kb_image_describe_status CHECK (describe_status IN ('pending', 'processing', 'done', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_kb_image_source_dirty ON kb_image_asset(source_id, embedding_dirty);
CREATE INDEX IF NOT EXISTS idx_kb_image_embedding ON kb_image_asset USING hnsw (embedding halfvec_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_kb_image_search_text_trgm ON kb_image_asset USING gin (search_text gin_trgm_ops);

CREATE TABLE IF NOT EXISTS kb_settings (
    id                  BIGSERIAL PRIMARY KEY CHECK (id = 1),
    hotwords            JSONB       NOT NULL DEFAULT '[]'::jsonb,    -- 金融热词表（注入清洗 prompt）
    segment_max_seconds INT         NOT NULL DEFAULT 30,
    asr_concurrency     INT         NOT NULL DEFAULT 2,
    top_k               INT         NOT NULL DEFAULT 8,
    auto_approve_points BOOLEAN     NOT NULL DEFAULT TRUE,           -- 抽取卡自动发布总开关（全绿卡免审直发）
    unit_prices         JSONB       NOT NULL DEFAULT '{}'::jsonb,    -- {asrPerHour, vlmPerImage} 参考单价
    embedding_config_id BIGINT REFERENCES llm_config(id) ON DELETE SET NULL,
    clean_model_id      BIGINT REFERENCES llm_config(id) ON DELETE SET NULL,
    extract_model_id    BIGINT REFERENCES llm_config(id) ON DELETE SET NULL,
    vision_model_id     BIGINT REFERENCES llm_config(id) ON DELETE SET NULL,
    authorized_user_ids JSONB       NOT NULL DEFAULT '[]'::jsonb,    -- 知识库授权白名单（admin 隐含）
    updated_by          BIGINT REFERENCES "user"(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_kb_settings_segment CHECK (segment_max_seconds BETWEEN 5 AND 120),
    CONSTRAINT chk_kb_settings_asr_concurrency CHECK (asr_concurrency BETWEEN 1 AND 8),
    CONSTRAINT chk_kb_settings_top_k CHECK (top_k BETWEEN 1 AND 50)
);

-- 缺省设置行（管理端「知识库设置」维护）
INSERT INTO kb_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING;
