-- 个股 AI 复盘数据缺失修复：
-- 1) financial-statement（东财三大报表）此前未注册任何采集任务，
--    financial_*_statement 仅存量手工数据，AI 复盘财务面长期 has_data: false
-- 2) stock-shares（tushare daily_basic 股本）：新浪交易所名单无沪市股本列，
--    沪市 stock_basic.total_shares 全量为 NULL，行情快照市值无法计算
--    （tushare stock_basic 接口不含股本字段，股本取自 daily_basic 每日指标）
-- 幂等可重复执行。

-- ============================================================
-- 1. 渠道接线：eastmoney + financial-statement / tushare + stock-shares
-- ============================================================

UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["financial-statement"]'::jsonb
WHERE source = 'eastmoney'
  AND NOT supported_data_types @> '["financial-statement"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'financial-statement', 1
FROM collector_channel_config
WHERE source = 'eastmoney'
ON CONFLICT (channel_id, data_type) DO NOTHING;

UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["stock-shares"]'::jsonb
WHERE source = 'tushare'
  AND NOT supported_data_types @> '["stock-shares"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'stock-shares', 1
FROM collector_channel_config
WHERE source = 'tushare'
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- ============================================================
-- 2. 定时任务
-- ============================================================

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES
    -- 财务报表季更，周六 11:00 全量刷新自选股（缺省 symbols = 全部自选股）；
    -- 首次启用/新加自选可后台手动执行立即回填
    ('eastmoney_financial_statement_weekly', 'financial-statement', 'eastmoney', '0 11 * * 6', true),
    -- 股本随公司行为低频变动，周六 03:00（晚于 sina_stock_list 02:00）全市场刷新
    ('tushare_stock_shares_weekly', 'stock-shares', 'tushare', '0 3 * * 6', true)
ON CONFLICT (task_name) DO NOTHING;
