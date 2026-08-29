-- ============================================================
-- 数据库命名规范重构迁移（旧 schema → 新 schema）
-- 说明：
-- 1. 仅重命名表与字段，使旧库结构与当前代码/01-schema.sql 对齐。
-- 2. 不强制重命名索引/约束名称（不影响应用运行）。
-- 3. 后续再按顺序执行 docker/database/migrations/ 下的增量迁移。
-- 4. 列重命名均通过 _rename_column_if_exists 条件执行，保证在
--    已是最终命名的全新库（01-schema.sql 初始化）上可重复执行。
-- ============================================================

-- 安全重命名辅助函数
CREATE OR REPLACE FUNCTION _rename_column_if_exists(
    p_table TEXT,
    p_old TEXT,
    p_new TEXT
) RETURNS void AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = p_table AND column_name = p_old
    ) THEN
        EXECUTE format('ALTER TABLE %I RENAME COLUMN %I TO %I', p_table, p_old, p_new);
    END IF;
END;
$$ LANGUAGE plpgsql;

-- 1. 用户域
ALTER TABLE IF EXISTS users RENAME TO "user";

-- 2. 行情域
ALTER TABLE IF EXISTS kline_daily RENAME TO quote_kline_stock_daily;
SELECT _rename_column_if_exists('quote_kline_stock_daily', 'pct_change', 'change_pct');

ALTER TABLE IF EXISTS kline_minute RENAME TO quote_kline_stock_minute;

ALTER TABLE IF EXISTS auction_data RENAME TO quote_auction_stock;

ALTER TABLE IF EXISTS index_auction RENAME TO quote_auction_index;

-- 3. 资金流向域
ALTER TABLE IF EXISTS fund_flow RENAME TO capital_fund_flow_stock;

ALTER TABLE IF EXISTS sector_fund_flow RENAME TO capital_fund_flow_sector;

-- 4. 股池域
ALTER TABLE IF EXISTS limit_up_pool RENAME TO pool_limit_up_stock;
SELECT _rename_column_if_exists('pool_limit_up_stock', 'break_count', 'broken_limit_count');
SELECT _rename_column_if_exists('pool_limit_up_stock', 'limit_stat', 'limit_status');

ALTER TABLE IF EXISTS dragon_list RENAME TO pool_dragon_tiger_stock;

-- 5. 财务报表域
ALTER TABLE IF EXISTS balance_sheet RENAME TO financial_balance_sheet;

ALTER TABLE IF EXISTS income_statement RENAME TO financial_income_statement;
SELECT _rename_column_if_exists('financial_income_statement', 'rd_expense', 'research_development_expense');

ALTER TABLE IF EXISTS cash_flow_statement RENAME TO financial_cash_flow_statement;
SELECT _rename_column_if_exists('financial_cash_flow_statement', 'cf_operations', 'cash_flow_from_operations');
SELECT _rename_column_if_exists('financial_cash_flow_statement', 'cf_investing', 'cash_flow_from_investing');
SELECT _rename_column_if_exists('financial_cash_flow_statement', 'cf_financing', 'cash_flow_from_financing');

-- 6. 产业链域
ALTER TABLE IF EXISTS company_chain_mapping RENAME TO industry_chain_company_mapping;
SELECT _rename_column_if_exists('industry_chain_company_mapping', 'position', 'chain_position');

SELECT _rename_column_if_exists('industry_chain_node', 'industry_l1', 'industry_level_1');

SELECT _rename_column_if_exists('industry_chain_edge', 'source', 'data_source');

-- 7. 基础标的域
SELECT _rename_column_if_exists('stock_basic', 'industry_l1', 'industry_level_1');
SELECT _rename_column_if_exists('stock_basic', 'industry_l2', 'industry_level_2');
SELECT _rename_column_if_exists('stock_basic', 'industry_l3', 'industry_level_3');

-- 8. 市场统计域
SELECT _rename_column_if_exists('market_breadth', 'stat_time', 'snapshot_time');
SELECT _rename_column_if_exists('market_breadth', 'broken_count', 'broken_limit_count');

-- 9. 文件域
SELECT _rename_column_if_exists('file_metadata', 'uploaded_at', 'created_at');

-- 10. 资讯域
SELECT _rename_column_if_exists('news_announcement', 'es_id', 'elasticsearch_doc_id');
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

-- 清理辅助函数
DROP FUNCTION IF EXISTS _rename_column_if_exists(TEXT, TEXT, TEXT);
