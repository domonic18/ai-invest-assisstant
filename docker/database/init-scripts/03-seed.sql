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

-- Default collector tasks
INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES
    ('ths_kline_daily', 'kline', 'ths', '0 16 * * 1-5', true),
    ('sina_index_kline', 'index-kline', 'sina', '30 15,18 * * 1-5', true),
    ('ths_auction', 'auction', 'ths', '15,25 9 * * 1-5', true),
    ('eastmoney_fund_flow', 'fund-flow', 'eastmoney', '0 17 * * 1-5', true),
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
    ('eastmoney_broken_pool', 'broken-pool', 'eastmoney', '40 15 * * 1-5', true),
    ('eastmoney_sector_fund_flow', 'sector-fund-flow', 'eastmoney', '30 17 * * 1-5', true),
    ('eastmoney_limit_up_pool', 'limit-up-pool', 'eastmoney', '35 15 * * 1-5', true),
    -- 须晚于 sina_market_breadth 最后一次写入（15:57），避免官方池家数被快照估算覆盖
    ('eastmoney_limit_down_pool', 'limit-down-pool', 'eastmoney', '0 16 * * 1-5', true),
    ('sina_etf_kline', 'etf-kline', 'sina', '5 16 * * 1-5', true),
    -- 须晚于 eastmoney_limit_up_pool（15:35），个股分钟线供涨停复盘分时缩略图
    ('sina_stock_minute', 'stock-minute', 'sina', '20 16,18 * * 1-5', true),
    -- A50 期指日盘 16:30 收盘，17:40 取当日日 K，21:40 夜盘修正
    ('eastmoney_a50_kline', 'a50-kline', 'eastmoney', '40 17,21 * * 1-5', true),
    -- 16:00 收盘后自动生成大盘综述 AI base，避免多租户重复调用 LLM
    ('market_daily_review_1600', 'market-daily-review', 'internal', '0 16 * * 1-5', true)
ON CONFLICT (task_name) DO NOTHING;
