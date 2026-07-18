-- Development seed data

-- Sample stocks
INSERT INTO stock_basic (stock_code, stock_name, market, industry_l1, industry_l2, industry_l3, listing_date)
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
    ('ths_auction', 'auction', 'ths', '15,25 9 * * 1-5', true),
    ('eastmoney_fund_flow', 'fund-flow', 'eastmoney', '0 17 * * 1-5', true),
    ('sina_news', 'news', 'sina', '0/30 * * * *', true),
    ('sina_stock_list', 'stock-list', 'sina', '0 2 * * 6', true),
    ('sina_quote', 'quote', 'sina', '*/5 9-15 * * 1-5', true),
    ('eastmoney_sector_fund_flow', 'sector-fund-flow', 'eastmoney', '30 17 * * 1-5', true),
    ('eastmoney_limit_up_pool', 'limit-up-pool', 'eastmoney', '35 15 * * 1-5', true)
ON CONFLICT (task_name) DO NOTHING;
