-- collector_task 实例级用途备注：任务配置页展示（remark 优先、TaskSpec 描述兜底）与编辑。
-- 背景：同一 task_type 存在多实例调度行（global-index / news-topic / index-auction），
-- 中文名与描述挂在类型上，实例仅靠英文 task_name 无法区分用途。
-- 幂等：可全量重放；重放会把备注重置为 seed 文案（03-seed.sql 末尾同款 UPDATE）。

ALTER TABLE collector_task ADD COLUMN IF NOT EXISTS remark VARCHAR(200);

-- global-index：同一数据域（全球指数 + 美债/日债收益率）按采集目的拆分的多实例
UPDATE collector_task SET remark = '盘中半小时级实时快照（COMEX 黄金/美元指数等外盘指标）'
 WHERE task_name = 'eastmoney_global_index_realtime';
UPDATE collector_task SET remark = '隔夜收盘定盘兜底（6/7 点覆盖美夏/冬令时收盘）'
 WHERE task_name = 'eastmoney_global_index_close';
UPDATE collector_task SET remark = '美债收益率日度（全量历史 upsert 幂等）'
 WHERE task_name = 'tushare_us_yield_daily';
UPDATE collector_task SET remark = '日债收益率日度（日本财务省 MOF 全量 CSV）'
 WHERE task_name = 'mof_jpy_yield_daily';
UPDATE collector_task SET remark = '港美股指数历史回补（手动触发，不排期）'
 WHERE task_name = 'yahoo_global_index_backfill';
UPDATE collector_task SET remark = 'Yahoo 全球指标每日幂等续期（USDCNY 增量 + HSTECH 自愈重试）'
 WHERE task_name = 'yahoo_global_index_daily';

-- news-topic：热点主题榜盘中/盘后双跑
UPDATE collector_task SET remark = '盘中热点主题榜（11:35，板块因子用 T-1 并标注）'
 WHERE task_name = 'news_topic_intraday';
UPDATE collector_task SET remark = '盘后热点主题榜（16:35，晚于板块收盘快照）'
 WHERE task_name = 'news_topic_post';

-- index-auction：竞价数据早盘采集 + 盘后补采兜底
UPDATE collector_task SET remark = '早盘集合竞价快照（9:26–9:29 采集 9:25 竞价成交额）'
 WHERE task_name = 'tushare_index_auction';
UPDATE collector_task SET remark = '盘后竞价数据补采兜底'
 WHERE task_name = 'tushare_index_auction_pm';
