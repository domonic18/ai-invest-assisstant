-- 批次 A 数据底座：全球指标日行情 / 跟踪指数配置 / 投资日历 / 财联社电报（幂等可重复执行）
-- quote_global_index_daily + tracked_index_config：A2 全球指标与工作台跟踪指数
-- calendar_event：A3 投资日历（含 FOMC/BLS 2026 官方日程种子，幂等）
-- news_telegraph：A1 财联社电报（驻留进程增量轮询，v1 仅 PG 不入 ES）

-- ============================================================
-- A2: 全球指数/指标日行情（COMEX 黄金、美元指数、美债收益率等）
-- ============================================================

CREATE TABLE IF NOT EXISTS quote_global_index_daily (
    index_code    VARCHAR(16)   NOT NULL,
    trade_date    DATE          NOT NULL,
    open          DECIMAL(16,4),
    high          DECIMAL(16,4),
    low           DECIMAL(16,4),
    close         DECIMAL(16,4),
    change_pct    DECIMAL(12,4),
    volume        BIGINT,
    amount        DECIMAL(20,2),
    source        VARCHAR(50),
    created_at    TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (index_code, trade_date)
);

SELECT create_hypertable('quote_global_index_daily', 'trade_date', chunk_time_interval => INTERVAL '1 year', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_quote_global_index_daily_code_date
    ON quote_global_index_daily(index_code, trade_date DESC);

-- ============================================================
-- A2: 跟踪指数配置（工作台/行情卡展示清单，Admin CRUD 管理）
-- ============================================================

CREATE TABLE IF NOT EXISTS tracked_index_config (
    id               BIGSERIAL PRIMARY KEY,
    index_code       VARCHAR(16)  NOT NULL,
    index_name       VARCHAR(100) NOT NULL,
    market_category  VARCHAR(10)  NOT NULL CONSTRAINT chk_tracked_index_config_market_category
                     CHECK (market_category IN ('A股', '全球')),
    data_source      VARCHAR(50)  NOT NULL,
    sort_order       INT          NOT NULL DEFAULT 100,
    is_enabled       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_tracked_index_config_index_code UNIQUE (index_code)
);

-- 默认 8 项：4 A 股指数（新浪）+ 4 全球指标（东财/tushare）
INSERT INTO tracked_index_config (index_code, index_name, market_category, data_source, sort_order, is_enabled)
VALUES
    ('sh000001', '上证指数',       'A股', 'sina',      1, true),
    ('sz399001', '深证成指',       'A股', 'sina',      2, true),
    ('sz399006', '创业板指',       'A股', 'sina',      3, true),
    ('sh000688', '科创50',         'A股', 'sina',      4, true),
    ('GC00Y',    'COMEX 黄金',     '全球', 'eastmoney', 5, true),
    ('DXY',      '美元指数',       '全球', 'eastmoney', 6, true),
    ('US2Y',     '美债 2Y 收益率', '全球', 'tushare',   7, true),
    ('US10Y',    '美债 10Y 收益率', '全球', 'tushare',  8, true)
ON CONFLICT (index_code) DO NOTHING;

-- ============================================================
-- A3: 投资日历事件（FOMC/BLS 官方日程等）
-- ============================================================

CREATE TABLE IF NOT EXISTS calendar_event (
    id              BIGSERIAL PRIMARY KEY,
    event_time      TIMESTAMPTZ  NOT NULL,
    end_time        TIMESTAMPTZ,
    title           VARCHAR(300) NOT NULL,
    category        VARCHAR(20)  NOT NULL CONSTRAINT chk_calendar_event_category
                    CHECK (category IN ('宏观', '央行动态', '新股', '解禁', '财报', '会议')),
    impact_markets  VARCHAR(50)[],
    source          VARCHAR(50),
    source_url      VARCHAR(1000),
    related_symbols TEXT[],
    source_hash     VARCHAR(32)  NOT NULL,          -- md5(source|event_time|title)，幂等键
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_calendar_event_source_hash UNIQUE (source_hash)
);

CREATE INDEX IF NOT EXISTS idx_calendar_event_time ON calendar_event(event_time);
CREATE INDEX IF NOT EXISTS idx_calendar_event_category_time ON calendar_event(category, event_time);

-- FOMC/BLS 2026 官方日程种子（federalreserve.gov / bls.gov 实抓；
-- FOMC 决议 = 议程第 2 日 14:00 ET，CPI/非农 = 08:30 ET，UTC 时刻已按美夏/冬令时换算）
-- 后续年度：每年 1 月新增迁移续写，ON CONFLICT (source_hash) DO NOTHING 幂等
INSERT INTO calendar_event (event_time, title, category, impact_markets, source, source_url, related_symbols, source_hash) VALUES
('2026-01-09 13:30:00+00', '美国非农就业数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/emp.htm', ARRAY['US10Y','DXY','GC00Y'], '5ada86512ff88920540d48f0c8d68410'),
('2026-01-13 13:30:00+00', '美国 CPI 通胀数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/cpi.htm', ARRAY['US10Y','DXY','GC00Y'], '310717f1cfcdbbfb1773a648b67810f0'),
('2026-01-28 19:00:00+00', '美联储 FOMC 利率决议', '央行动态', ARRAY['美股','美债','美元','黄金'], 'fomc', 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm', ARRAY['US10Y','US2Y','DXY','GC00Y'], '7d9ab859a6d92df63158fc388746463e'),
('2026-02-11 13:30:00+00', '美国非农就业数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/emp.htm', ARRAY['US10Y','DXY','GC00Y'], '1b3217748b418bf7093de3af29db1d52'),
('2026-02-13 13:30:00+00', '美国 CPI 通胀数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/cpi.htm', ARRAY['US10Y','DXY','GC00Y'], 'a81e4f526f8134db5f3b7280698cffbe'),
('2026-03-06 13:30:00+00', '美国非农就业数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/emp.htm', ARRAY['US10Y','DXY','GC00Y'], '04d0e62b21a64e6808171e31ca2e6d09'),
('2026-03-11 12:30:00+00', '美国 CPI 通胀数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/cpi.htm', ARRAY['US10Y','DXY','GC00Y'], '491f6a1c5019ee3d1c8bc9e573d44922'),
('2026-03-18 18:00:00+00', '美联储 FOMC 利率决议', '央行动态', ARRAY['美股','美债','美元','黄金'], 'fomc', 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm', ARRAY['US10Y','US2Y','DXY','GC00Y'], '7dae77ff06f09974bcc270ec55920840'),
('2026-04-03 12:30:00+00', '美国非农就业数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/emp.htm', ARRAY['US10Y','DXY','GC00Y'], 'ab6a183b04fe089330f745848b5bf374'),
('2026-04-10 12:30:00+00', '美国 CPI 通胀数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/cpi.htm', ARRAY['US10Y','DXY','GC00Y'], 'e134f51d5f40907c7d6d1e2c8f191904'),
('2026-04-29 18:00:00+00', '美联储 FOMC 利率决议', '央行动态', ARRAY['美股','美债','美元','黄金'], 'fomc', 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm', ARRAY['US10Y','US2Y','DXY','GC00Y'], '4c28c434108012bbce547e9052706292'),
('2026-05-08 12:30:00+00', '美国非农就业数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/emp.htm', ARRAY['US10Y','DXY','GC00Y'], 'bf00c4fe4ed205cfae0e51e8fb94eb0d'),
('2026-05-12 12:30:00+00', '美国 CPI 通胀数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/cpi.htm', ARRAY['US10Y','DXY','GC00Y'], 'ca02f703b04c1b52b7ef5939f8e6cf2e'),
('2026-06-05 12:30:00+00', '美国非农就业数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/emp.htm', ARRAY['US10Y','DXY','GC00Y'], '596875055b5f4fdc7a9958d997e83398'),
('2026-06-10 12:30:00+00', '美国 CPI 通胀数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/cpi.htm', ARRAY['US10Y','DXY','GC00Y'], '3a52c920b3a843bb339a59062e68d4cd'),
('2026-06-17 18:00:00+00', '美联储 FOMC 利率决议', '央行动态', ARRAY['美股','美债','美元','黄金'], 'fomc', 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm', ARRAY['US10Y','US2Y','DXY','GC00Y'], '9cf4a7ba256806fdb7044f9981e9da38'),
('2026-07-02 12:30:00+00', '美国非农就业数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/emp.htm', ARRAY['US10Y','DXY','GC00Y'], '07b064681a7cc82d71712eb057d7d592'),
('2026-07-14 12:30:00+00', '美国 CPI 通胀数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/cpi.htm', ARRAY['US10Y','DXY','GC00Y'], '0e695964446d6f899032c1dce330e1e2'),
('2026-07-29 18:00:00+00', '美联储 FOMC 利率决议', '央行动态', ARRAY['美股','美债','美元','黄金'], 'fomc', 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm', ARRAY['US10Y','US2Y','DXY','GC00Y'], '32d7bf07bccdbba3f6bcc29a5c6509e8'),
('2026-08-07 12:30:00+00', '美国非农就业数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/emp.htm', ARRAY['US10Y','DXY','GC00Y'], '8ebf697d4910e41c4bbe27debda54d59'),
('2026-08-12 12:30:00+00', '美国 CPI 通胀数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/cpi.htm', ARRAY['US10Y','DXY','GC00Y'], 'ee993baf3f0f7d95e6d4965d69b3df56'),
('2026-09-04 12:30:00+00', '美国非农就业数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/emp.htm', ARRAY['US10Y','DXY','GC00Y'], '24891af1bab17af158c848613581ba51'),
('2026-09-11 12:30:00+00', '美国 CPI 通胀数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/cpi.htm', ARRAY['US10Y','DXY','GC00Y'], '5a8acdb70fd5e5cd9deeed79728b135f'),
('2026-09-16 18:00:00+00', '美联储 FOMC 利率决议', '央行动态', ARRAY['美股','美债','美元','黄金'], 'fomc', 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm', ARRAY['US10Y','US2Y','DXY','GC00Y'], 'bda13d0848df907f1af4a5060c3f20a1'),
('2026-10-02 12:30:00+00', '美国非农就业数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/emp.htm', ARRAY['US10Y','DXY','GC00Y'], '9d102de9da9d6c744afb467b962f9d41'),
('2026-10-14 12:30:00+00', '美国 CPI 通胀数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/cpi.htm', ARRAY['US10Y','DXY','GC00Y'], '1510a60d336146cbaa40c26bd72dbceb'),
('2026-10-28 18:00:00+00', '美联储 FOMC 利率决议', '央行动态', ARRAY['美股','美债','美元','黄金'], 'fomc', 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm', ARRAY['US10Y','US2Y','DXY','GC00Y'], 'beca6c1e922e31b3a8d9f3dd1514b377'),
('2026-11-06 13:30:00+00', '美国非农就业数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/emp.htm', ARRAY['US10Y','DXY','GC00Y'], '56da1a6b66a3d0d0b9de850015663353'),
('2026-11-10 13:30:00+00', '美国 CPI 通胀数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/cpi.htm', ARRAY['US10Y','DXY','GC00Y'], 'a888904731810af53d29860062101cf5'),
('2026-12-04 13:30:00+00', '美国非农就业数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/emp.htm', ARRAY['US10Y','DXY','GC00Y'], '4ea2c71f6ddf8572fc02ffc57002aacd'),
('2026-12-09 19:00:00+00', '美联储 FOMC 利率决议', '央行动态', ARRAY['美股','美债','美元','黄金'], 'fomc', 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm', ARRAY['US10Y','US2Y','DXY','GC00Y'], 'b9092f7a568310de2b6db378bb572040'),
('2026-12-10 13:30:00+00', '美国 CPI 通胀数据发布', '宏观', ARRAY['美股','美债','美元','黄金'], 'bls', 'https://www.bls.gov/schedule/news_release/cpi.htm', ARRAY['US10Y','DXY','GC00Y'], 'cd797738527eca7aed1e05985d9207ee')
ON CONFLICT (source_hash) DO NOTHING;

-- ============================================================
-- A1: 财联社电报（stream 驻留进程 10s 增量轮询，cls_msg_id 幂等）
-- ============================================================

CREATE TABLE IF NOT EXISTS news_telegraph (
    id            BIGSERIAL PRIMARY KEY,
    cls_msg_id    BIGINT       NOT NULL,
    title         VARCHAR(500),
    content       TEXT,
    category      VARCHAR(50),                       -- cls type 字段原值
    importance    SMALLINT,                          -- cls level 字段
    shared        SMALLINT,
    stock_codes   TEXT[],
    extra         JSONB,                             -- 其余 cls 字段（brief/shareurl 等）
    publish_time  TIMESTAMPTZ  NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_news_telegraph_cls_msg_id UNIQUE (cls_msg_id)
);

CREATE INDEX IF NOT EXISTS idx_news_telegraph_publish_time ON news_telegraph(publish_time DESC);

-- ============================================================
-- 采集任务与渠道关联
-- ============================================================

-- 防御性补齐 eastmoney/tushare 渠道的 global-index 数据类型（渠道已存在时）
UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["global-index"]'::jsonb
WHERE source IN ('eastmoney', 'tushare')
  AND NOT supported_data_types @> '["global-index"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT c.id, d.data_type, 1
FROM collector_channel_config c
CROSS JOIN (VALUES ('global-index')) AS d(data_type)
WHERE c.source IN ('eastmoney', 'tushare')
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- cls 渠道（签名自持无需 api_key，入目录便于管理）
INSERT INTO collector_channel_config (source, name, is_enabled, supported_data_types)
VALUES ('cls', '财联社', true, '["cls-telegraph-backfill"]'::jsonb)
ON CONFLICT (source) DO NOTHING;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'cls-telegraph-backfill', 1
FROM collector_channel_config
WHERE source = 'cls'
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- 渠道解析按 TaskSpec.name 匹配 collector_channel_data_type.data_type，
-- 同一任务类型的多条调度行（实时/收盘/美债）镜像 index-auction 的多行模式
INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES
    -- 盘中半小时级实时快照（COMEX 黄金/美元指数，push2delay 镜像）
    ('eastmoney_global_index_realtime', 'global-index', 'eastmoney', '*/30 9-17 * * 1-5', true),
    -- 美股收盘定盘兜底（北京时间 6/7 点覆盖美夏/冬令时收盘）
    ('eastmoney_global_index_close', 'global-index', 'eastmoney', '0 6,7 * * 2-6', true),
    -- 美债收益率日度（us_tycr 单次返回全量历史，upsert 幂等）
    ('tushare_us_yield_daily', 'global-index', 'tushare', '30 6 * * 2-6', true),
    -- cls 电报历史回补：手动触发不排 cron，增量由 stream 驻留进程负责
    ('cls_telegraph_backfill', 'cls-telegraph-backfill', 'cls', NULL, false)
ON CONFLICT (task_name) DO UPDATE
SET task_type = EXCLUDED.task_type, source = EXCLUDED.source;
