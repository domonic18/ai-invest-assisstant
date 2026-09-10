-- 资讯快讯数据源归一：news 任务 source 从 sina 迁至 eastmoney（幂等可重复执行）
-- sina_news 原为东财个股新闻（写死 000001），改为东财全球快讯（市场级）；
-- sina 渠道保留行情类任务，news 数据类型移交 eastmoney 渠道。

-- 1. collector_channel_config：sina 移除 news，eastmoney 追加 news
UPDATE collector_channel_config
SET supported_data_types = supported_data_types - 'news'
WHERE source = 'sina'
  AND supported_data_types ? 'news';

UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["news"]'::jsonb
WHERE source = 'eastmoney'
  AND NOT supported_data_types @> '["news"]'::jsonb;

-- 2. collector_channel_data_type：删 (sina, news)，加 (eastmoney, news)
DELETE FROM collector_channel_data_type d
USING collector_channel_config c
WHERE d.channel_id = c.id
  AND c.source = 'sina'
  AND d.data_type = 'news';

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT c.id, 'news', 1
FROM collector_channel_config c
WHERE c.source = 'eastmoney'
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- 3. collector_task：sina_news → eastmoney_flash_news，source sina→eastmoney
UPDATE collector_task
SET task_name = 'eastmoney_flash_news', source = 'eastmoney'
WHERE task_name = 'sina_news'
  AND task_type = 'news';
