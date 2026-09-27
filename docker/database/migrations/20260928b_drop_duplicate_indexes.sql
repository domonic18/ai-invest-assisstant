-- 20260928b_drop_duplicate_indexes.sql
-- 存储体检（2026-09-27）P1：清理与 UNIQUE 约束索引完全同列的手工重复索引。
-- 13 组均为「约束唯一索引 + 同列普通 idx 并存」（btree 双写放大、体积翻倍），
-- 保留约束那份即可同时服务唯一性与查询（btree 可反向扫描，DESC/ASC 等价）。
-- mapping_stock_concept 的 pkey(id) 与 uq(stock_code, concept_code) 列不同，非重复，勿动。

-- 分时线（hypertable，pkey (stock_code, trade_time)）
DROP INDEX IF EXISTS idx_kline_minute_code_time;              -- ≡ kline_minute_pkey

-- 竞价快照（uq (stock_code, trade_date, match_time)）
DROP INDEX IF EXISTS idx_auction_code_date_time;              -- ≡ auction_data_stock_code_trade_date_match_time_key

-- 个股资金流（hypertable，pkey (stock_code, trade_date)）
DROP INDEX IF EXISTS idx_fund_flow_code_date;                 -- ≡ fund_flow_pkey

-- 财务三表（uq (stock_code, report_date)）
DROP INDEX IF EXISTS idx_balance_sheet_code_date;             -- ≡ balance_sheet_stock_code_report_date_key
DROP INDEX IF EXISTS idx_income_statement_code_date;          -- ≡ income_statement_stock_code_report_date_key
DROP INDEX IF EXISTS idx_cash_flow_code_date;                 -- ≡ cash_flow_statement_stock_code_report_date_key

-- 用户邮箱（uq email）
DROP INDEX IF EXISTS idx_users_email;                         -- ≡ users_email_key

-- 采集日志（uq celery_task_id）
DROP INDEX IF EXISTS idx_collector_log_celery_task_id;        -- ≡ uq_collector_log_celery_task_id

-- 个股日K（hypertable，pkey (stock_code, trade_date)）
DROP INDEX IF EXISTS idx_kline_daily_code_date;               -- ≡ kline_daily_pkey1

-- 个人复盘（uq (user_id, trade_date)）
DROP INDEX IF EXISTS idx_user_market_review_user_date;        -- ≡ user_market_review_user_id_trade_date_key

-- 全球指数日K（hypertable，pkey (index_code, trade_date)）
DROP INDEX IF EXISTS idx_quote_global_index_daily_code_date;  -- ≡ quote_global_index_daily_pkey

-- AI 画线（uq (user_id, target_type, target_code, period)）
DROP INDEX IF EXISTS idx_ai_kline_drawing_scope;              -- ≡ uq_ai_kline_drawing

-- 模拟盘现金快照（uq (paper_trade_account_id, trade_date)）
DROP INDEX IF EXISTS idx_paper_trade_cash_snapshot_account_date;  -- ≡ uq_paper_trade_cash_snapshot_account_date
