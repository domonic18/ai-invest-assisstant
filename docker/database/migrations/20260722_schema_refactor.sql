-- ============================================================
-- 数据库命名规范重构迁移（旧 schema → 新 schema）
-- 说明：
-- 1. 仅重命名表与字段，使旧库结构与当前代码/01-schema.sql 对齐。
-- 2. 不强制重命名索引/约束名称（不影响应用运行）。
-- 3. 后续再按顺序执行 docker/database/migrations/ 下的增量迁移。
-- ============================================================

-- 1. 用户域
ALTER TABLE IF EXISTS users RENAME TO "user";
ALTER TABLE IF EXISTS "user" RENAME COLUMN password_hash TO password_hash;  -- 无变化，占位保持可读

-- 2. 行情域
ALTER TABLE IF EXISTS kline_daily RENAME TO quote_kline_stock_daily;
ALTER TABLE IF EXISTS quote_kline_stock_daily RENAME COLUMN pct_change TO change_pct;

ALTER TABLE IF EXISTS kline_minute RENAME TO quote_kline_stock_minute;

ALTER TABLE IF EXISTS auction_data RENAME TO quote_auction_stock;

ALTER TABLE IF EXISTS index_auction RENAME TO quote_auction_index;

-- 3. 资金流向域
ALTER TABLE IF EXISTS fund_flow RENAME TO capital_fund_flow_stock;

ALTER TABLE IF EXISTS sector_fund_flow RENAME TO capital_fund_flow_sector;

-- 4. 股池域
ALTER TABLE IF EXISTS limit_up_pool RENAME TO pool_limit_up_stock;
ALTER TABLE IF EXISTS pool_limit_up_stock RENAME COLUMN break_count TO broken_limit_count;
ALTER TABLE IF EXISTS pool_limit_up_stock RENAME COLUMN limit_stat TO limit_status;

ALTER TABLE IF EXISTS dragon_list RENAME TO pool_dragon_tiger_stock;

-- 5. 财务报表域
ALTER TABLE IF EXISTS balance_sheet RENAME TO financial_balance_sheet;

ALTER TABLE IF EXISTS income_statement RENAME TO financial_income_statement;
ALTER TABLE IF EXISTS financial_income_statement RENAME COLUMN rd_expense TO research_development_expense;

ALTER TABLE IF EXISTS cash_flow_statement RENAME TO financial_cash_flow_statement;
ALTER TABLE IF EXISTS financial_cash_flow_statement RENAME COLUMN cf_operations TO cash_flow_from_operations;
ALTER TABLE IF EXISTS financial_cash_flow_statement RENAME COLUMN cf_investing TO cash_flow_from_investing;
ALTER TABLE IF EXISTS financial_cash_flow_statement RENAME COLUMN cf_financing TO cash_flow_from_financing;

-- 6. 产业链域
ALTER TABLE IF EXISTS company_chain_mapping RENAME TO industry_chain_company_mapping;
ALTER TABLE IF EXISTS industry_chain_company_mapping RENAME COLUMN position TO chain_position;

ALTER TABLE IF EXISTS industry_chain_node RENAME COLUMN industry_l1 TO industry_level_1;

ALTER TABLE IF EXISTS industry_chain_edge RENAME COLUMN source TO data_source;

-- 7. 基础标的域
ALTER TABLE IF EXISTS stock_basic RENAME COLUMN industry_l1 TO industry_level_1;
ALTER TABLE IF EXISTS stock_basic RENAME COLUMN industry_l2 TO industry_level_2;
ALTER TABLE IF EXISTS stock_basic RENAME COLUMN industry_l3 TO industry_level_3;

-- 8. 市场统计域
ALTER TABLE IF EXISTS market_breadth RENAME COLUMN stat_time TO snapshot_time;
ALTER TABLE IF EXISTS market_breadth RENAME COLUMN broken_count TO broken_limit_count;

-- 9. 文件域
ALTER TABLE IF EXISTS file_metadata RENAME COLUMN uploaded_at TO created_at;

-- 10. 资讯域
ALTER TABLE IF EXISTS news_announcement RENAME COLUMN es_id TO elasticsearch_doc_id;
ALTER TABLE IF EXISTS news_announcement ADD COLUMN IF NOT EXISTS extra JSONB DEFAULT '{}'::jsonb;

-- 11. 配置域
ALTER TABLE IF EXISTS llm_configs RENAME TO llm_config;

ALTER TABLE IF EXISTS collector_channel_configs RENAME TO collector_channel_config;

ALTER TABLE IF EXISTS collector_channel_data_types RENAME TO collector_channel_data_type;

-- 12. 基金持仓域
ALTER TABLE IF EXISTS fund_holdings RENAME TO fund_holding;

-- 13. 重命名序列（可选，保持命名一致）
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'users_id_seq') THEN
        ALTER SEQUENCE users_id_seq RENAME TO user_id_seq;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'kline_daily_stock_code_seq') THEN
        ALTER SEQUENCE kline_daily_stock_code_seq RENAME TO quote_kline_stock_daily_stock_code_seq;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'llm_configs_id_seq') THEN
        ALTER SEQUENCE llm_configs_id_seq RENAME TO llm_config_id_seq;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'collector_channel_configs_id_seq') THEN
        ALTER SEQUENCE collector_channel_configs_id_seq RENAME TO collector_channel_config_id_seq;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'collector_channel_data_types_id_seq') THEN
        ALTER SEQUENCE collector_channel_data_types_id_seq RENAME TO collector_channel_data_type_id_seq;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'fund_holdings_id_seq') THEN
        ALTER SEQUENCE fund_holdings_id_seq RENAME TO fund_holding_id_seq;
    END IF;
END $$;
