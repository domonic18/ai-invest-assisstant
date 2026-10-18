-- COMEX 白银 / COMEX 铜纳入全球跟踪指标：
-- 注册表 GLOBAL_INDEX_CODES 已登记（eastmoney secid 101.SI00Y / 101.HG00Y，
-- yahoo SI=F / HG=F 历史回填），此处补跟踪配置行使其进入
-- 宏观监测/工作台指数快览展示清单。
INSERT INTO tracked_index_config (index_code, index_name, market_category, data_source, sort_order, is_enabled)
VALUES
    ('SI00Y', 'COMEX 白银', '全球', 'eastmoney', 23, true),
    ('HG00Y', 'COMEX 铜',   '全球', 'eastmoney', 24, true)
ON CONFLICT (index_code) DO NOTHING;
