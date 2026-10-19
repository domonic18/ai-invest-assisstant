-- 港股支持 P0：行情底座（主数据 + 日 K + 快照 + 自选市场维度）
--   1) user_watchlist 增加 market 列（NULL=存量 A 股，sh/sz/bj 由 stock_basic 回填）
--   2) eastmoney 渠道补齐 hk-stock-list / hk-kline，sina 渠道补齐 hk-quote
--   3) 三条调度行：主数据（开市前）、日 K（收盘后）、快照（盘中 15 分钟级）
--      港股交易日历 P0 未引入（A/H 假期不同），trade_day_only=false，靠幂等重跑兜底
-- 幂等：条件 UPDATE / ON CONFLICT DO NOTHING·DO UPDATE；重放无副作用。

ALTER TABLE user_watchlist ADD COLUMN IF NOT EXISTS market VARCHAR(4);

-- stock_basic.market 原有 CHECK 约束仅含 sh/sz/bj，港股需放开
ALTER TABLE stock_basic DROP CONSTRAINT IF EXISTS stock_basic_market_check;
ALTER TABLE stock_basic ADD CONSTRAINT stock_basic_market_check
  CHECK (market::text = ANY (ARRAY['sh'::varchar, 'sz'::varchar, 'bj'::varchar, 'hk'::varchar]));

UPDATE user_watchlist w
SET market = sb.market
FROM stock_basic sb
WHERE sb.stock_code = w.stock_code
  AND w.market IS NULL
  AND sb.market IN ('sh', 'sz', 'bj');

UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["hk-stock-list", "hk-kline"]'::jsonb
WHERE source = 'eastmoney'
  AND NOT supported_data_types @> '["hk-stock-list"]'::jsonb;

UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["hk-quote"]'::jsonb
WHERE source = 'sina'
  AND NOT supported_data_types @> '["hk-quote"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, t.data_type, 1
FROM collector_channel_config c
CROSS JOIN (VALUES ('hk-stock-list'), ('hk-kline')) AS t(data_type)
WHERE c.source = 'eastmoney'
ON CONFLICT (channel_id, data_type) DO NOTHING;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'hk-quote', 1
FROM collector_channel_config
WHERE source = 'sina'
ON CONFLICT (channel_id, data_type) DO NOTHING;

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active, trade_day_only)
VALUES
    -- 港股开市前刷新全市场主数据（东财 fs=m:116+t:3 正股口径）
    ('eastmoney_hk_stock_list', 'hk-stock-list', 'eastmoney', '40 8 * * 1-5', true, false),
    -- 港股收盘（16:00 HKT + 收市竞价）后日 K 增量，前复权，默认 5 日幂等续期
    ('eastmoney_hk_kline', 'hk-kline', 'eastmoney', '40 16 * * 1-5', true, false),
    -- 盘中全市场快照（新浪，延时 15 分钟），写 Redis 供行情接口读取
    ('sina_hk_quote', 'hk-quote', 'sina', '*/15 9-16 * * 1-5', true, false)
ON CONFLICT (task_name) DO UPDATE
SET task_type = EXCLUDED.task_type, source = EXCLUDED.source;

UPDATE collector_task SET remark = '港股全市场列表主数据（东财 fs=m:116+t:3 正股口径）'
 WHERE task_name = 'eastmoney_hk_stock_list';
UPDATE collector_task SET remark = '港股日 K 前复权（东财 secid=116，全市场宇宙）'
 WHERE task_name = 'eastmoney_hk_kline';
UPDATE collector_task SET remark = '港股全市场快照（新浪 rt_hk 系，延时 15 分钟）'
 WHERE task_name = 'sina_hk_quote';

-- 国企指数跟踪配置（secid=100.HSCEI，随每日「全球指标行情」任务采集；
-- 用户须在个人设置勾选后才会出现在工作台指数条）
INSERT INTO tracked_index_config (index_code, index_name, market_category, data_source, sort_order, is_enabled)
VALUES ('HSCEI', '国企指数', '全球', 'eastmoney', 22, true)
ON CONFLICT (index_code) DO NOTHING;
