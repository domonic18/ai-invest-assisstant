-- 韩国综合指数（KOSPI）纳入全球跟踪指标：
-- 注册表 GLOBAL_INDEX_CODES 已登记（eastmoney secid 100.KS11 / yahoo ^KS11 历史回填），
-- 此处补跟踪配置行使其进入宏观监测/工作台指数快览展示清单。
INSERT INTO tracked_index_config (index_code, index_name, market_category, data_source, sort_order, is_enabled)
VALUES
    ('KS11', '韩国综合指数', '全球', 'eastmoney', 22, true)
ON CONFLICT (index_code) DO NOTHING;
