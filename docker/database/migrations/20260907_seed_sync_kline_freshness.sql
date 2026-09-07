-- 存量环境同步 03-seed.sql 两笔变更（新建库自动生效，存量库需本迁移；幂等可重复执行）：
--   be96bcf：kline-freshness 任务登记 + ths_kline_daily 渠道 ths→sina
--   c1b0391：market_daily_review_1600 任务名对齐实际调度时刻 → 1630

-- ths 渠道已因东财 WAF 弃用，日 K 统一走 sina 全历史 upsert（spec 中 kline 仅剩 sina 采集器）
UPDATE collector_task
SET source = 'sina'
WHERE task_name = 'ths_kline_daily'
  AND source = 'ths';

-- internal 渠道登记 kline-freshness 数据类型
UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["kline-freshness"]'::jsonb
WHERE source = 'internal'
  AND NOT supported_data_types @> '["kline-freshness"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'kline-freshness', 1
FROM collector_channel_config
WHERE source = 'internal'
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- 交易日晚间校验自选股/指数/ETF/A50 日 K 覆盖最近交易日，缺失重跑采集自愈（heavy 队列，
-- 18:30/21:00 双档兜底新浪当日 bar 发布滞后；数据已齐时为良性 SKIPPED）
INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES ('kline_freshness_evening', 'kline-freshness', 'internal', '30 18,21 * * 1-5', true)
ON CONFLICT (task_name) DO NOTHING;

-- 任务名对齐实际 cron（16:30 收盘批）；代码按 task_type 引用任务，改名安全。
-- 加存在性守卫：若 1630 已存在（如手工建过）则跳过，避免唯一键冲突。
UPDATE collector_task
SET task_name = 'market_daily_review_1630'
WHERE task_name = 'market_daily_review_1600'
  AND NOT EXISTS (SELECT 1 FROM collector_task WHERE task_name = 'market_daily_review_1630');
