-- 20260923b: 异动检测融入趋势理论——板块/个股异动表加 trend_facts 事实列，
-- 板块检测调度移至 17:45（板块日 K 17:30 采集完成后才有当日 bar 供趋势维）。
-- 幂等：重复执行无副作用。
ALTER TABLE market_anomaly_sector
    ADD COLUMN IF NOT EXISTS trend_facts JSONB;
ALTER TABLE market_anomaly_stock
    ADD COLUMN IF NOT EXISTS trend_facts JSONB;

UPDATE collector_task
SET task_name = 'sector_anomaly_detect_1745',
    schedule = '45 17 * * 1-5'
WHERE task_name = 'sector_anomaly_detect_1645';
