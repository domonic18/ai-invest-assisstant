-- 宏观监测扩展指标：美债 30Y / 四汇率对 / 布伦特原油（幂等可重复执行）
-- tracked_index_config 增 6 行；collector_task 增 yahoo 每日幂等任务
-- （USDCNY 无东财源 + HSTECH Yahoo 已下线，均靠该任务 1y 全量 upsert 续期）

INSERT INTO tracked_index_config (index_code, index_name, market_category, data_source, sort_order, is_enabled)
VALUES
    ('US30Y',  '美债 30Y 收益率', '全球', 'tushare',   16, true),
    ('USDCNY', '美元/人民币',     '全球', 'yahoo',     17, true),
    ('USDCNH', '美元/离岸人民币', '全球', 'eastmoney', 18, true),
    ('USDJPY', '美元/日元',       '全球', 'eastmoney', 19, true),
    ('USDEUR', '美元/欧元',       '全球', 'eastmoney', 20, true),
    ('B00Y',   '布伦特原油',      '全球', 'eastmoney', 21, true)
ON CONFLICT (index_code) DO NOTHING;

-- Yahoo 全球指标每日幂等续期（07:30 mof/cme 批次后错峰；1y 全量 upsert，
-- 承担 USDCNY 每日增量 + HSTECH 404 自愈重试 + 新 symbol 上线自动纳入）
INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES
    ('yahoo_global_index_daily', 'global-index', 'yahoo', '40 7 * * *', true)
ON CONFLICT (task_name) DO UPDATE
SET task_type = EXCLUDED.task_type, source = EXCLUDED.source;
