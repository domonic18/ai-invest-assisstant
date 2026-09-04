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

-- market_daily_review_1600 / limit_up_ai_review_1630 / stock_daily_analysis_1640 /
-- chain_refresh_weekly / collector_log_cleanup_daily 任务的 internal 渠道（内部生成，非外部数据源）
-- supported_data_types 与 collector_channel_data_type 按任务名登记（渠道解析/beat 派发以任务名为键）
INSERT INTO collector_channel_config (source, name, is_enabled, supported_data_types)
VALUES ('internal', '内部生成', true, '["market-daily-review", "limit-up-ai-review", "stock-daily-analysis", "chain-refresh", "collector-log-cleanup"]'::jsonb)
ON CONFLICT (source) DO NOTHING;

-- 兼容存量环境：internal 渠道已存在时补齐后续新增的数据类型
UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["stock-daily-analysis", "chain-refresh", "collector-log-cleanup"]'::jsonb
WHERE source = 'internal'
  AND NOT supported_data_types @> '["chain-refresh"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, d.data_type, 1
FROM collector_channel_config,
     (VALUES ('market-daily-review'), ('limit-up-ai-review'), ('stock-daily-analysis'), ('chain-refresh'), ('collector-log-cleanup')) AS d(data_type)
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
    -- 16:40 遍历开启 AI 复盘分组的自选股逐只生成个股分析，晚于大盘复盘
    ('stock_daily_analysis_1640', 'ai_stock_daily_analysis', 'internal', '40 16 * * 1-5', true),
    -- 周六 06:00 对已有成功版本的产业链重新 AI 分析并落新版本（非交易日运行，无交易日门控）
    ('chain_refresh_weekly', 'chain-refresh', 'internal', '0 6 * * 6', true),
    -- 每日 03:40 清理 90 天前的采集执行日志
    ('collector_log_cleanup_daily', 'collector-log-cleanup', 'internal', '40 3 * * *', true),
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
VALUES ('cls', '财联社', true, '["cls-telegraph-backfill", "cls-investkalendar"]'::jsonb)
ON CONFLICT (source) DO NOTHING;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, d.data_type, 1
FROM collector_channel_config
CROSS JOIN (VALUES ('cls-telegraph-backfill'), ('cls-investkalendar')) AS d(data_type)
WHERE source = 'cls'
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- 渠道解析按 TaskSpec.name 匹配 collector_channel_data_type.data_type，
-- 同一任务类型的多条调度行（实时/收盘/美债）镜像 index-auction 的多行模式
INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES
    -- 盘中半小时级实时快照（COMEX 黄金/美元指数，push2delay 镜像）
    ('eastmoney_global_index_realtime', 'global-index', 'eastmoney', '*/30 9-17 * * 1-5', true),
    -- 美股收盘定盘兜底（北京时间 6/7 点覆盖美夏/冬令时收盘）
    ('eastmoney_global_index_close', 'global-index', 'eastmoney', '0 6,7 * * 2-6', true),
    -- 美债收益率日度（us_tycr 单次返回全量历史，upsert 幂等）
    ('tushare_us_yield_daily', 'global-index', 'tushare', '30 6 * * 2-6', true),
    -- cls 电报历史回补：手动触发不排 cron，增量由 stream 驻留进程负责
    ('cls_telegraph_backfill', 'cls-telegraph-backfill', 'cls', NULL, false),
    -- cls 投资日历：每日 07:15 拉取前瞻窗口（含周末会议，不设星期过滤）
    ('cls_investkalendar_daily', 'cls-investkalendar', 'cls', '15 7 * * *', true)
ON CONFLICT (task_name) DO UPDATE
SET task_type = EXCLUDED.task_type, source = EXCLUDED.source;

-- FOMC/BLS 2026 官方日程种子（federalreserve.gov / bls.gov 实抓；
-- FOMC 决议 = 议程第 2 日 14:00 ET，CPI/非农 = 08:30 ET，UTC 时刻已按美夏/冬令时换算）
-- 后续年度：每年 1 月新增迁移续写，ON CONFLICT (source_hash) DO NOTHING 幂等
INSERT INTO calendar_event (event_time, title, category, impact_markets, source, source_url, related_symbols, source_hash) VALUES
('2026-01-09 13:30:00+00', '美国非农就业数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/emp.htm', ARRAY['US10Y','DXY','GC00Y'], '5ada86512ff88920540d48f0c8d68410'),
('2026-01-13 13:30:00+00', '美国 CPI 通胀数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/cpi.htm', ARRAY['US10Y','DXY','GC00Y'], '310717f1cfcdbbfb1773a648b67810f0'),
('2026-01-28 19:00:00+00', '美联储 FOMC 利率决议', '央行动态', ARRAY['美股','美债','美元','黄金'], 'fomc', 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm', ARRAY['US10Y','US2Y','DXY','GC00Y'], '7d9ab859a6d92df63158fc388746463e'),
('2026-02-11 13:30:00+00', '美国非农就业数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/emp.htm', ARRAY['US10Y','DXY','GC00Y'], '1b3217748b418bf7093de3af29db1d52'),
('2026-02-13 13:30:00+00', '美国 CPI 通胀数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/cpi.htm', ARRAY['US10Y','DXY','GC00Y'], 'a81e4f526f8134db5f3b7280698cffbe'),
('2026-03-06 13:30:00+00', '美国非农就业数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/emp.htm', ARRAY['US10Y','DXY','GC00Y'], '04d0e62b21a64e6808171e31ca2e6d09'),
('2026-03-11 12:30:00+00', '美国 CPI 通胀数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/cpi.htm', ARRAY['US10Y','DXY','GC00Y'], '491f6a1c5019ee3d1c8bc9e573d44922'),
('2026-03-18 18:00:00+00', '美联储 FOMC 利率决议', '央行动态', ARRAY['美股','美债','美元','黄金'], 'fomc', 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm', ARRAY['US10Y','US2Y','DXY','GC00Y'], '7dae77ff06f09974bcc270ec55920840'),
('2026-04-03 12:30:00+00', '美国非农就业数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/emp.htm', ARRAY['US10Y','DXY','GC00Y'], 'ab6a183b04fe089330f745848b5bf374'),
('2026-04-10 12:30:00+00', '美国 CPI 通胀数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/cpi.htm', ARRAY['US10Y','DXY','GC00Y'], 'e134f51d5f40907c7d6d1e2c8f191904'),
('2026-04-29 18:00:00+00', '美联储 FOMC 利率决议', '央行动态', ARRAY['美股','美债','美元','黄金'], 'fomc', 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm', ARRAY['US10Y','US2Y','DXY','GC00Y'], '4c28c434108012bbce547e9052706292'),
('2026-05-08 12:30:00+00', '美国非农就业数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/emp.htm', ARRAY['US10Y','DXY','GC00Y'], 'bf00c4fe4ed205cfae0e51e8fb94eb0d'),
('2026-05-12 12:30:00+00', '美国 CPI 通胀数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/cpi.htm', ARRAY['US10Y','DXY','GC00Y'], 'ca02f703b04c1b52b7ef5939f8e6cf2e'),
('2026-06-05 12:30:00+00', '美国非农就业数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/emp.htm', ARRAY['US10Y','DXY','GC00Y'], '596875055b5f4fdc7a9958d997e83398'),
('2026-06-10 12:30:00+00', '美国 CPI 通胀数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/cpi.htm', ARRAY['US10Y','DXY','GC00Y'], '3a52c920b3a843bb339a59062e68d4cd'),
('2026-06-17 18:00:00+00', '美联储 FOMC 利率决议', '央行动态', ARRAY['美股','美债','美元','黄金'], 'fomc', 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm', ARRAY['US10Y','US2Y','DXY','GC00Y'], '9cf4a7ba256806fdb7044f9981e9da38'),
('2026-07-02 12:30:00+00', '美国非农就业数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/emp.htm', ARRAY['US10Y','DXY','GC00Y'], '07b064681a7cc82d71712eb057d7d592'),
('2026-07-14 12:30:00+00', '美国 CPI 通胀数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/cpi.htm', ARRAY['US10Y','DXY','GC00Y'], '0e695964446d6f899032c1dce330e1e2'),
('2026-07-29 18:00:00+00', '美联储 FOMC 利率决议', '央行动态', ARRAY['美股','美债','美元','黄金'], 'fomc', 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm', ARRAY['US10Y','US2Y','DXY','GC00Y'], '32d7bf07bccdbba3f6bcc29a5c6509e8'),
('2026-08-07 12:30:00+00', '美国非农就业数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/emp.htm', ARRAY['US10Y','DXY','GC00Y'], '8ebf697d4910e41c4bbe27debda54d59'),
('2026-08-12 12:30:00+00', '美国 CPI 通胀数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/cpi.htm', ARRAY['US10Y','DXY','GC00Y'], 'ee993baf3f0f7d95e6d4965d69b3df56'),
('2026-09-04 12:30:00+00', '美国非农就业数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/emp.htm', ARRAY['US10Y','DXY','GC00Y'], '24891af1bab17af158c848613581ba51'),
('2026-09-11 12:30:00+00', '美国 CPI 通胀数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/cpi.htm', ARRAY['US10Y','DXY','GC00Y'], '5a8acdb70fd5e5cd9deeed79728b135f'),
('2026-09-16 18:00:00+00', '美联储 FOMC 利率决议', '央行动态', ARRAY['美股','美债','美元','黄金'], 'fomc', 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm', ARRAY['US10Y','US2Y','DXY','GC00Y'], 'bda13d0848df907f1af4a5060c3f20a1'),
('2026-10-02 12:30:00+00', '美国非农就业数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/emp.htm', ARRAY['US10Y','DXY','GC00Y'], '9d102de9da9d6c744afb467b962f9d41'),
('2026-10-14 12:30:00+00', '美国 CPI 通胀数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/cpi.htm', ARRAY['US10Y','DXY','GC00Y'], '1510a60d336146cbaa40c26bd72dbceb'),
('2026-10-28 18:00:00+00', '美联储 FOMC 利率决议', '央行动态', ARRAY['美股','美债','美元','黄金'], 'fomc', 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm', ARRAY['US10Y','US2Y','DXY','GC00Y'], 'beca6c1e922e31b3a8d9f3dd1514b377'),
('2026-11-06 13:30:00+00', '美国非农就业数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/emp.htm', ARRAY['US10Y','DXY','GC00Y'], '56da1a6b66a3d0d0b9de850015663353'),
('2026-11-10 13:30:00+00', '美国 CPI 通胀数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/cpi.htm', ARRAY['US10Y','DXY','GC00Y'], 'a888904731810af53d29860062101cf5'),
('2026-12-04 13:30:00+00', '美国非农就业数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/emp.htm', ARRAY['US10Y','DXY','GC00Y'], '4ea2c71f6ddf8572fc02ffc57002aacd'),
('2026-12-09 19:00:00+00', '美联储 FOMC 利率决议', '央行动态', ARRAY['美股','美债','美元','黄金'], 'fomc', 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm', ARRAY['US10Y','US2Y','DXY','GC00Y'], 'b9092f7a568310de2b6db378bb572040'),
('2026-12-10 13:30:00+00', '美国 CPI 通胀数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/cpi.htm', ARRAY['US10Y','DXY','GC00Y'], 'cd797738527eca7aed1e05985d9207ee')
ON CONFLICT (source_hash) DO NOTHING;
