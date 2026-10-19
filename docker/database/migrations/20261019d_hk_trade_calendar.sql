-- 港股交易日历：market 维度 + HKEX 官方休市日种子
-- market_trade_calendar 由单市场（A 股）扩为多市场：加 market 列并重建复合
-- 主键 (calendar_date, market)，存量行归 market='cn'，A 股口径不受影响
-- （repository/service 全部带 market 缺省参数，缺省 'cn'）。
-- collector_task 加 market 列；三只 hk-* 任务置 market='hk' 且
-- trade_day_only=true：非 A/H 重合的港方假日（圣诞/复活节/重阳等）调度
-- 预检直接 SKIPPED，不再空跑（2026-10-19 重阳节 hk-kline 空跑约 38 分钟）。
-- 休市种子来源（港交所官方通告，证券市场周六日及下表日期休市）：
--   2026: ce_SEHK_CT_075_2025（2025-06-02 发出）
--   2027: ce_SEHK_CT_077_2026（2026-06-01 发出）
-- 半日市（农历年廿九/圣诞前夕/新年前夕）对 EOD 采集口径无影响，不单独标记。

ALTER TABLE market_trade_calendar
    ADD COLUMN IF NOT EXISTS market VARCHAR(4) NOT NULL DEFAULT 'cn';

ALTER TABLE market_trade_calendar DROP CONSTRAINT market_trade_calendar_pkey;
ALTER TABLE market_trade_calendar ADD PRIMARY KEY (calendar_date, market);

WITH holidays(calendar_date, holiday) AS (VALUES
    ('2026-01-01'::date, '元旦'),
    ('2026-02-17'::date, '农历年初一'),
    ('2026-02-18'::date, '农历年初二'),
    ('2026-02-19'::date, '农历年初三'),
    ('2026-04-03'::date, '耶稣受难节'),
    ('2026-04-06'::date, '清明节翌日'),
    ('2026-04-07'::date, '复活节星期一翌日'),
    ('2026-05-01'::date, '劳动节'),
    ('2026-05-25'::date, '佛诞翌日'),
    ('2026-06-19'::date, '端午节'),
    ('2026-07-01'::date, '香港特别行政区成立纪念日'),
    ('2026-10-01'::date, '国庆节'),
    ('2026-10-19'::date, '重阳节翌日'),
    ('2026-12-25'::date, '圣诞节'),
    ('2027-01-01'::date, '元旦'),
    ('2027-02-08'::date, '农历年初三'),
    ('2027-02-09'::date, '农历年初四'),
    ('2027-03-26'::date, '耶稣受难节'),
    ('2027-03-29'::date, '复活节星期一'),
    ('2027-04-05'::date, '清明节'),
    ('2027-05-13'::date, '佛诞'),
    ('2027-06-09'::date, '端午节'),
    ('2027-07-01'::date, '香港特别行政区成立纪念日'),
    ('2027-09-16'::date, '中秋节翌日'),
    ('2027-10-01'::date, '国庆节'),
    ('2027-10-08'::date, '重阳节'),
    ('2027-12-27'::date, '圣诞节后首个平日')
),
days AS (
    SELECT generate_series(
        '2026-01-01'::date, '2027-12-31'::date, interval '1 day'
    )::date AS d
)
INSERT INTO market_trade_calendar (calendar_date, market, is_trading, source, remark)
SELECT
    d,
    'hk',
    (extract(isodow FROM d) < 6 AND h.calendar_date IS NULL),
    'seed',
    h.holiday
FROM days
LEFT JOIN holidays h ON h.calendar_date = days.d
ON CONFLICT (calendar_date, market) DO UPDATE
SET is_trading = excluded.is_trading,
    remark = excluded.remark,
    updated_at = now()
WHERE market_trade_calendar.source = 'seed';

ALTER TABLE collector_task
    ADD COLUMN IF NOT EXISTS market VARCHAR(4) NOT NULL DEFAULT 'cn';

UPDATE collector_task
SET market = 'hk', trade_day_only = TRUE
WHERE task_name IN ('eastmoney_hk_stock_list', 'eastmoney_hk_kline', 'sina_hk_quote');
