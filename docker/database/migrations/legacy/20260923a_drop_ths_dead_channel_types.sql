-- 20260923a: 清理 ths 渠道无采集器实现的任务关联（concept-constituents / kline）
-- 背景：同花顺概念成分接口随 akshare 1.14.17 移除后，concept-constituents 仅剩
-- eastmoney 实现；kline 的 ths 渠道也已因 WAF 弃用。残留的渠道关联会让解析器
-- 每晚把无实现渠道排进 fallback 链，collector_log 每次必记一条
-- 「渠道没有任务对应的采集器」错误噪音。
-- 幂等：重复执行无副作用。
DELETE FROM collector_channel_data_type dt
USING collector_channel_config c
WHERE dt.channel_id = c.id
  AND c.source = 'ths'
  AND dt.data_type IN ('concept-constituents', 'kline');

UPDATE collector_channel_config
SET supported_data_types = supported_data_types - 'concept-constituents' - 'kline'
WHERE source = 'ths'
  AND (supported_data_types @> '["concept-constituents"]'::jsonb
       OR supported_data_types @> '["kline"]'::jsonb);
