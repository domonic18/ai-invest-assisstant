-- 20260928c_tsdb_minute_retention_sector_compress.sql
-- 存储体检（2026-09-27）P2：分钟线加 14 天 drop 保留 + 板块日K补 90 天压缩策略。
-- 分钟线：全消费方最深回看 2 个交易日（分时图/自选 sparkline/复盘技术面），
-- 新浪渠道历史分钟线仅 ~8 个交易日可回补，14 天窗口（= 压缩窗口）封顶表体积；
-- 板块日K：不在批次 D 三条压缩策略内（32MB 未压缩），同模式补齐。
-- 幂等检查查 timescaledb_information.jobs（TimescaleDB 2.28 无
-- compression_policies / retention_policies 视图）。

-- 分钟线 14 天 drop（chunk 7 天，整 chunk 超窗即删）
DO $$
DECLARE
    job_count int;
BEGIN
    SELECT count(*) INTO job_count
    FROM timescaledb_information.jobs
    WHERE proc_name = 'policy_retention'
      AND hypertable_name = 'quote_kline_stock_minute';
    IF job_count = 0 THEN
        PERFORM add_retention_policy(
            'quote_kline_stock_minute', INTERVAL '14 days'
        );
    END IF;
END $$;

-- 板块日K压缩（chunk 1 年，策略实际压缩发生在整 chunk 超窗后；
-- 当前年份 chunk 内新写入不受影响）
ALTER TABLE quote_kline_sector_daily SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'sector_code',
    timescaledb.compress_orderby = 'trade_date'
);

DO $$
DECLARE
    job_count int;
BEGIN
    SELECT count(*) INTO job_count
    FROM timescaledb_information.jobs
    WHERE proc_name = 'policy_compression'
      AND hypertable_name = 'quote_kline_sector_daily';
    IF job_count = 0 THEN
        PERFORM add_compression_policy(
            'quote_kline_sector_daily', INTERVAL '90 days'
        );
    END IF;
END $$;
