-- D30 排程重排补漏：交易复盘 16:10→19:00、每日计划 19:00→19:30（北京时区）。
-- D30 重排（commit f355559）只改了 init-scripts/03-seed.sql，无迁移携带新时刻；
-- 而既有库的行由 20260926c/26d 种入（旧时刻，ON CONFLICT 不更新 schedule），
-- 导致生产等存量环境永久停留在漂移时刻——复盘会早于 18:35 大盘复盘触发，
-- 核心输入缺失。本迁移把两实例拨回与 03-seed.sql 一致的目标时刻。
-- 幂等：仅当 schedule 与目标不一致时更新；新初始化库（seed 已正确）为 no-op。

UPDATE collector_task SET schedule = '0 19 * * 1-5'
WHERE task_name = 'paper_trade_review_1610' AND schedule IS DISTINCT FROM '0 19 * * 1-5';

UPDATE collector_task SET schedule = '30 19 * * 1-5'
WHERE task_name = 'agent_daily_plan_1900' AND schedule IS DISTINCT FROM '30 19 * * 1-5';
