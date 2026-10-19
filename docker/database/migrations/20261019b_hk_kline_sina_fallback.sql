-- 港股日 K 新浪备源渠道接线
-- 东财 push2his 偶发 WAF 封禁，hk-kline 增加新浪（akshare stock_hk_daily
-- 前复权）fallback 渠道：东财保持 priority 1 主源，新浪 priority 2 备源。
-- 注意：需在应用启动（seed_default_channels）之前执行，保证优先级不被
-- 种子逻辑按渠道声明序抢先写成 1。

-- 东财 hk-kline 行统一钉在主源优先级
UPDATE collector_channel_data_type d
SET priority = 1
FROM collector_channel_config c
WHERE c.id = d.channel_id
  AND c.source = 'eastmoney'
  AND d.data_type = 'hk-kline';

-- 新浪 hk-kline 备源行（缺失插入；已存在则校正为备源优先级）
INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT c.id, 'hk-kline', 2
FROM collector_channel_config c
WHERE c.source = 'sina'
ON CONFLICT (channel_id, data_type) DO UPDATE SET priority = 2;
