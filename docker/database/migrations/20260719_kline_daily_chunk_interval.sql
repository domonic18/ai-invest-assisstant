-- 重建 quote_kline_stock_daily：chunk 间隔从默认 7 天调整为 1 年
-- 日 K 横跨数十年，7 天 chunk 会产生 1800+ 个 chunk；TimescaleDB 规划时
-- 需逐 chunk 做约束排除，规划耗时高达数百毫秒（执行仅几毫秒）。
-- 1 年 chunk 将数量降到每年 1 个，规划开销可忽略。
-- 旧表逐 chunk DROP 会超出 max_locks_per_transaction，故按年分批 drop_chunks。
-- 幂等：kline_daily_old 不存在时各步骤自动跳过。

DO $$
DECLARE
    chunk_count int;
BEGIN
    SELECT count(*) INTO chunk_count
    FROM timescaledb_information.chunks
    WHERE hypertable_name = 'quote_kline_stock_daily';

    IF chunk_count > 100 THEN
        ALTER TABLE quote_kline_stock_daily RENAME TO kline_daily_old;
        ALTER INDEX idx_kline_daily_code_date RENAME TO idx_kline_daily_code_date_old;

        CREATE TABLE quote_kline_stock_daily (
            stock_code    VARCHAR(10)   NOT NULL,
            trade_date    DATE          NOT NULL,
            open          DECIMAL(12,3),
            high          DECIMAL(12,3),
            low           DECIMAL(12,3),
            close         DECIMAL(12,3),
            volume        BIGINT,
            amount        DECIMAL(20,2),
            amplitude     DECIMAL(8,2),
            change_pct    DECIMAL(8,2),
            turnover_rate DECIMAL(8,2),
            created_at    TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (stock_code, trade_date)
        );

        PERFORM create_hypertable(
            'quote_kline_stock_daily', 'trade_date',
            chunk_time_interval => INTERVAL '1 year',
            if_not_exists => TRUE
        );
        CREATE INDEX idx_kline_daily_code_date
            ON quote_kline_stock_daily(stock_code, trade_date DESC);

        INSERT INTO quote_kline_stock_daily SELECT * FROM kline_daily_old;
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '1992-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '1993-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '1994-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '1995-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '1996-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '1997-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '1998-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '1999-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2000-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2001-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2002-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2003-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2004-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2005-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2006-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2007-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2008-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2009-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2010-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2011-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2012-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2013-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2014-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2015-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2016-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2017-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2018-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2019-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2020-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2021-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2022-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2023-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2024-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2025-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2026-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2027-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2028-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2029-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2030-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        PERFORM drop_chunks('kline_daily_old', DATE '2031-01-01');
    END IF;
END $$;

DO $$ BEGIN
    IF to_regclass('kline_daily_old') IS NOT NULL THEN
        DROP TABLE kline_daily_old;
    END IF;
END $$;
