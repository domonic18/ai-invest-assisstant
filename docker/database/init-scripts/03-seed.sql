-- Development seed data

-- Sample stocks
INSERT INTO stock_basic (stock_code, stock_name, market, industry_level_1, industry_level_2, industry_level_3, listing_date)
VALUES
    ('000001', '平安银行', 'sz', '银行', '股份制银行', '银行III', '1991-04-03'),
    ('000002', '万科A', 'sz', '房地产', '房地产开发', '住宅开发', '1991-01-29'),
    ('000333', '美的集团', 'sz', '家用电器', '白色家电', '空调', '2013-09-18'),
    ('000858', '五粮液', 'sz', '食品饮料', '白酒', '白酒III', '1998-04-27'),
    ('002594', '比亚迪', 'sz', '汽车', '乘用车', '电动乘用车', '2011-06-30'),
    ('600000', '浦发银行', 'sh', '银行', '股份制银行', '银行III', '1999-11-10'),
    ('600009', '上海机场', 'sh', '交通运输', '机场', '机场III', '1998-02-18'),
    ('600519', '贵州茅台', 'sh', '食品饮料', '白酒', '白酒III', '2001-08-27'),
    ('600036', '招商银行', 'sh', '银行', '股份制银行', '银行III', '2002-04-09'),
    ('601318', '中国平安', 'sh', '非银金融', '保险', '保险III', '2007-03-01')
ON CONFLICT (stock_code, market) DO NOTHING;

-- market_daily_review_1600 / limit_up_ai_review_1630 任务的 internal 渠道（内部生成，非外部数据源）
INSERT INTO collector_channel_config (source, name, is_enabled, supported_data_types)
VALUES ('internal', '内部生成', true, '["market-daily-review", "limit-up-ai-review"]'::jsonb)
ON CONFLICT (source) DO NOTHING;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, d.data_type, 1
FROM collector_channel_config,
     (VALUES ('market-daily-review'), ('limit-up-ai-review')) AS d(data_type)
WHERE source = 'internal'
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- 防御性补齐 eastmoney 渠道的 research-report 数据类型（渠道已存在时）
UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["research-report"]'::jsonb
WHERE source = 'eastmoney'
  AND NOT supported_data_types @> '["research-report"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'research-report', 1
FROM collector_channel_config
WHERE source = 'eastmoney'
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- Default collector tasks
INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES
    ('ths_kline_daily', 'kline', 'ths', '0 16 * * 1-5', true),
    ('sina_index_kline', 'index-kline', 'sina', '0 16,18 * * 1-5', true),
    ('ths_auction', 'auction', 'ths', '15,25 9 * * 1-5', true),
    ('eastmoney_fund_flow', 'fund-flow', 'eastmoney', '0 16 * * 1-5', true),
    ('sina_news', 'news', 'sina', '0/30 * * * *', true),
    ('sina_stock_list', 'stock-list', 'sina', '0 2 * * 6', true),
    ('sina_quote', 'quote', 'sina', '*/5 9-15 * * 1-5', true),
    ('sina_market_breadth', 'market-breadth', 'sina', '2-57/5 9-15 * * 1-5', true),
    ('sina_index_spot', 'index-spot', 'sina', '* 9-15 * * 1-5', true),
    ('sina_index_minute', 'index-minute', 'sina', '* 9-15 * * 1-5', true),
    -- 9:33 首根分钟 bar 落库后采集指数 9:25 竞价成交额，15:33 补采兜底
    ('tushare_index_auction', 'index-auction', 'tushare', '26-29 9 * * 1-5', true),
    ('tushare_index_auction_pm', 'index-auction', 'tushare', '35 16 * * 1-5', true),
    ('exchange_market_amount', 'market-amount', 'exchange', '40 15,16,17 * * 1-5', true),
    ('eastmoney_broken_pool', 'broken-pool', 'eastmoney', '0 16 * * 1-5', true),
    ('eastmoney_sector_fund_flow', 'sector-fund-flow', 'eastmoney', '0 16 * * 1-5', true),
    ('eastmoney_limit_up_pool', 'limit-up-pool', 'eastmoney', '0 16 * * 1-5', true),
    -- 须晚于 sina_market_breadth 最后一次写入（15:57），避免官方池家数被快照估算覆盖
    ('eastmoney_limit_down_pool', 'limit-down-pool', 'eastmoney', '0 16 * * 1-5', true),
    ('sina_etf_kline', 'etf-kline', 'sina', '5 16 * * 1-5', true),
    -- 须晚于 eastmoney_limit_up_pool（16:00），个股分钟线供涨停复盘分时缩略图
    ('sina_stock_minute', 'stock-minute', 'sina', '20 16,18 * * 1-5', true),
    -- A50 期指日盘 16:30 收盘，17:40 取当日日 K，21:40 夜盘修正
    ('eastmoney_a50_kline', 'a50-kline', 'eastmoney', '40 17,21 * * 1-5', true),
    -- 16:00 收盘批数据就绪后生成大盘综述 AI base，避免多租户重复调用 LLM
    ('market_daily_review_1600', 'market-daily-review', 'internal', '30 16 * * 1-5', true),
    -- 16:30 涨停股池（16:00 批次）落库后生成涨停 AI 归因，与复盘同批串行执行
    ('limit_up_ai_review_1630', 'limit-up-ai-review', 'internal', '30 16 * * 1-5', true),
    -- 研报每日 8 点/18 点采集（东财 reportapi 列表 + PDF 落 MinIO）
    ('eastmoney_research_report', 'research-report', 'eastmoney', '0 8,18 * * *', true)
ON CONFLICT (task_name) DO NOTHING;

-- ============================================================
-- 批次 A：跟踪指数默认配置 + 全球指标/cls 电报采集任务
-- ============================================================

INSERT INTO tracked_index_config (index_code, index_name, market_category, data_source, sort_order, is_enabled)
VALUES
    ('sh000001', '上证指数',       'A股', 'sina',      1, true),
    ('sz399001', '深证成指',       'A股', 'sina',      2, true),
    ('sz399006', '创业板指',       'A股', 'sina',      3, true),
    ('sh000688', '科创50',         'A股', 'sina',      4, true),
    ('GC00Y',    'COMEX 黄金',     '全球', 'eastmoney', 5, true),
    ('DXY',      '美元指数',       '全球', 'eastmoney', 6, true),
    ('US2Y',     '美债 2Y 收益率', '全球', 'tushare',   7, true),
    ('US10Y',    '美债 10Y 收益率', '全球', 'tushare',  8, true)
ON CONFLICT (index_code) DO NOTHING;

-- 防御性补齐 eastmoney/tushare 渠道的 global-index 数据类型（渠道已存在时）
UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["global-index"]'::jsonb
WHERE source IN ('eastmoney', 'tushare')
  AND NOT supported_data_types @> '["global-index"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT c.id, d.data_type, 1
FROM collector_channel_config c
CROSS JOIN (VALUES ('global-index')) AS d(data_type)
WHERE c.source IN ('eastmoney', 'tushare')
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- cls 渠道（签名自持无需 api_key，入目录便于管理）
INSERT INTO collector_channel_config (source, name, is_enabled, supported_data_types)
VALUES ('cls', '财联社', true, '["news-telegraph"]'::jsonb)
ON CONFLICT (source) DO NOTHING;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'news-telegraph', 1
FROM collector_channel_config
WHERE source = 'cls'
ON CONFLICT (channel_id, data_type) DO NOTHING;

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES
    -- 盘中半小时级实时快照（COMEX 黄金/美元指数，push2delay 镜像）
    ('eastmoney_global_index_realtime', 'global-index-realtime', 'eastmoney', '*/30 9-17 * * 1-5', true),
    -- 美股收盘定盘兜底（北京时间 6/7 点覆盖美夏/冬令时收盘）
    ('eastmoney_global_index_close', 'global-index-close', 'eastmoney', '0 6,7 * * 2-6', true),
    -- 美债收益率日度（us_tycr 单次返回全量历史，upsert 幂等）
    ('tushare_us_yield_daily', 'us-yield-daily', 'tushare', '30 6 * * 2-6', true),
    -- cls 电报历史回补：手动触发不排 cron，增量由 stream 驻留进程负责
    ('cls_telegraph_backfill', 'cls-telegraph-backfill', 'cls', NULL, false)
ON CONFLICT (task_name) DO NOTHING;
