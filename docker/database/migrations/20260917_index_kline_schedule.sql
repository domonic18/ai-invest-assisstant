-- 新浪指数日 K 的当日 bar 源端约 18:00 才可用（实测稳定 18:00 落地，深市偶发 18:30、
-- 沪深300ETF 迟至 21:30），16:00 采集永远拿不到当天数据。AI 复盘（16:30）的指数
-- 行情已改由实时快照兜底（index_quotation_service.get_index_quotes），日 K 采集
-- 收敛为 18:00 单次，18:30/21:30 由 kline_freshness_evening 兜底补缺。
UPDATE collector_task
SET schedule = '0 18 * * 1-5'
WHERE task_name = 'sina_index_kline'
  AND schedule <> '0 18 * * 1-5';
