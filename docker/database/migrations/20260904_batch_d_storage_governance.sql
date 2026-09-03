-- 批次 D 存储治理三件套（幂等可重复执行）
-- ① TimescaleDB 压缩策略：分钟线（收益最大）/日 K/个股资金流
-- ② collector_log 90 天保留：存量一次性清理 + 每日清理任务登记
-- ③ LangGraph checkpoint 孤儿 thread 清理（assistant_session 已删但 checkpoint 残留）

-- ============================================================
-- ① 压缩策略
-- 排除 quote_global_index_daily：us_tycr 每日全历史 upsert 会写旧 chunk
-- （压缩段只读），且表体量小（4 code × 日行）压缩收益趋零。
-- kline 日线 chunk 为 1 年粒度，策略实际压缩发生在整 chunk 超窗后（2027 起），
-- 当前年份 chunk 内新写入不受影响。
-- ============================================================

ALTER TABLE quote_kline_stock_minute SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'stock_code',
    timescaledb.compress_orderby = 'trade_time'
);

ALTER TABLE quote_kline_stock_daily SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'stock_code',
    timescaledb.compress_orderby = 'trade_date'
);

ALTER TABLE capital_fund_flow_stock SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'stock_code',
    timescaledb.compress_orderby = 'trade_date'
);

-- 分钟线 14 天后压缩（chunk 默认 7 天，收益最大）；日表 90 天，
-- 为盘后回补/修正留足可写窗口
DO $$
DECLARE
    job_count int;
BEGIN
    SELECT count(*) INTO job_count
    FROM timescaledb_information.compression_policies
    WHERE hypertable_name = 'quote_kline_stock_minute';
    IF job_count = 0 THEN
        PERFORM add_compression_policy(
            'quote_kline_stock_minute', INTERVAL '14 days'
        );
    END IF;

    SELECT count(*) INTO job_count
    FROM timescaledb_information.compression_policies
    WHERE hypertable_name = 'quote_kline_stock_daily';
    IF job_count = 0 THEN
        PERFORM add_compression_policy(
            'quote_kline_stock_daily', INTERVAL '90 days'
        );
    END IF;

    SELECT count(*) INTO job_count
    FROM timescaledb_information.compression_policies
    WHERE hypertable_name = 'capital_fund_flow_stock';
    IF job_count = 0 THEN
        PERFORM add_compression_policy(
            'capital_fund_flow_stock', INTERVAL '90 days'
        );
    END IF;
END $$;

-- ============================================================
-- ② collector_log 保留策略
-- 表为普通表（PK 是 id，转 hypertable 需改 PK 破坏性大），走任务清理：
-- 存量一次性 DELETE + collector-log-cleanup 每日 03:40 任务
-- ============================================================

DELETE FROM collector_log
WHERE started_at < NOW() - INTERVAL '90 days';

UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["collector-log-cleanup"]'::jsonb
WHERE source = 'internal'
  AND NOT supported_data_types @> '["collector-log-cleanup"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'collector-log-cleanup', 1
FROM collector_channel_config
WHERE source = 'internal'
ON CONFLICT (channel_id, data_type) DO NOTHING;

INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES ('collector_log_cleanup_daily', 'collector-log-cleanup', 'internal', '40 3 * * *', true)
ON CONFLICT (task_name) DO NOTHING;

-- ============================================================
-- ③ LangGraph checkpoint 孤儿 thread 清理
-- checkpoint 三表由 AsyncPostgresSaver.setup() 运行时创建，新鲜环境无表时跳过；
-- 增量防护由 assistant_service.delete_session 先删 thread 再删行保证
-- ============================================================

DO $$
DECLARE
    orphan_count int;
BEGIN
    IF to_regclass('public.checkpoints') IS NULL
       OR to_regclass('public.checkpoint_blobs') IS NULL
       OR to_regclass('public.checkpoint_writes') IS NULL THEN
        RAISE NOTICE 'langgraph checkpoint tables not present, skipping';
        RETURN;
    END IF;

    SELECT count(*) INTO orphan_count
    FROM checkpoints c
    WHERE NOT EXISTS (
        SELECT 1 FROM assistant_session s WHERE s.id::text = c.thread_id
    );

    IF orphan_count > 0 THEN
        DELETE FROM checkpoint_writes w
        WHERE NOT EXISTS (
            SELECT 1 FROM assistant_session s WHERE s.id::text = w.thread_id
        );
        DELETE FROM checkpoint_blobs b
        WHERE NOT EXISTS (
            SELECT 1 FROM assistant_session s WHERE s.id::text = b.thread_id
        );
        DELETE FROM checkpoints c
        WHERE NOT EXISTS (
            SELECT 1 FROM assistant_session s WHERE s.id::text = c.thread_id
        );
        RAISE NOTICE 'cleaned % orphan checkpoint threads', orphan_count;
    END IF;
END $$;
