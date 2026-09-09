-- 迭代 4 资讯中心 AI 增强：事件故事线 / 用户订阅命中 / 热点主题快照（幂等可重复执行）
-- 故事线为全局内容（AI 自动建线 + 手动建线共用一张表，origin/user_id 区分）；
-- 用户级「停止跟踪」只影响本人视图（user_news_storyline），AI 续接全局进行

-- 1. 事件故事线（全局）
CREATE TABLE IF NOT EXISTS news_storyline (
    id            BIGSERIAL PRIMARY KEY,
    title         VARCHAR(200) NOT NULL,
    summary       TEXT,
    status        VARCHAR(16) NOT NULL DEFAULT 'tracking' CONSTRAINT chk_news_storyline_status
                  CHECK (status IN ('tracking', 'near_end', 'finished')),
    origin        VARCHAR(8)  NOT NULL DEFAULT 'ai' CONSTRAINT chk_news_storyline_origin
                  CHECK (origin IN ('ai', 'manual')),
    user_id       BIGINT REFERENCES "user"(id) ON DELETE CASCADE,   -- 手动建线者（AI 线为 NULL）
    report_count  INT NOT NULL DEFAULT 0,
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_seen_at  TIMESTAMPTZ NOT NULL,
    latest_brief  TEXT,
    nodes         JSONB,                                -- 节点链 [{time, brief}]
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_news_storyline_status
    ON news_storyline(status, last_seen_at DESC);

-- 2. 用户级跟踪操作（active=默认跟踪中，stopped=本人不再展示）
CREATE TABLE IF NOT EXISTS user_news_storyline (
    user_id      BIGINT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    storyline_id BIGINT NOT NULL REFERENCES news_storyline(id) ON DELETE CASCADE,
    action       VARCHAR(8) NOT NULL DEFAULT 'active' CONSTRAINT chk_user_news_storyline_action
                 CHECK (action IN ('active', 'stopped')),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, storyline_id)
);

-- 3. 线内条目：一条资讯至多入一条线（UQ(source, item_id) 保证续接幂等、防重复入线）
CREATE TABLE IF NOT EXISTS news_storyline_item (
    storyline_id BIGINT NOT NULL REFERENCES news_storyline(id) ON DELETE CASCADE,
    source       VARCHAR(32) NOT NULL,                  -- 与 news_ai_score.source 同口径
    item_id      VARCHAR(64) NOT NULL,                  -- 源表业务主键（电报=cls_msg_id）
    added_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (storyline_id, source, item_id),
    CONSTRAINT uq_news_storyline_item_item UNIQUE (source, item_id)
);

-- 4. 我的订阅：关键词命中回流电报流
CREATE TABLE IF NOT EXISTS user_news_subscription (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    keyword      VARCHAR(100) NOT NULL,
    channels     JSONB,                                 -- 命中渠道过滤（NULL/空=全部渠道）
    push_enabled BOOLEAN NOT NULL DEFAULT FALSE,        -- 推送通道实装前仅存配置
    enabled      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_news_subscription_user_keyword UNIQUE (user_id, keyword)
);

-- 5. 订阅命中记录：电报流 ★ 标注 / 仅看订阅命中按 (source, item_id) 探查
CREATE TABLE IF NOT EXISTS news_subscription_hit (
    subscription_id BIGINT NOT NULL REFERENCES user_news_subscription(id) ON DELETE CASCADE,
    source          VARCHAR(32) NOT NULL,
    item_id         VARCHAR(64) NOT NULL,
    hit_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (subscription_id, source, item_id)
);

CREATE INDEX IF NOT EXISTS idx_news_subscription_hit_item
    ON news_subscription_hit(source, item_id);

-- 6. 热点主题快照：盘中/盘后双跑（LLM 聚类 + 库内热度因子拼装，input_hash 同输入跳过）
CREATE TABLE IF NOT EXISTS news_topic_snapshot (
    trade_date   DATE NOT NULL,
    session      VARCHAR(8) NOT NULL CONSTRAINT chk_news_topic_snapshot_session
                 CHECK (session IN ('intraday', 'post')),
    topics       JSONB,                                 -- [{title, sentiment, votes, item_ids, chain, heat, factors, asOfTradeDate}]
    wordcloud    JSONB,                                 -- [{word, count}]
    input_hash   VARCHAR(64),
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (trade_date, session)
);

-- internal 渠道补登本迭代数据类型（渠道解析按任务名匹配 collector_channel_data_type，
-- 缺关联行时 run_task 以 SKIPPED「没有启用任何可用的采集渠道」结束——迭代 3 教训）
UPDATE collector_channel_config
SET supported_data_types = supported_data_types
    || '["news-storyline", "news-subscription-match", "news-topic"]'::jsonb
WHERE source = 'internal'
  AND NOT supported_data_types @> '["news-storyline"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT c.id, d.data_type, 1
FROM collector_channel_config c,
     (VALUES ('news-storyline'), ('news-subscription-match'), ('news-topic')) AS d(data_type)
WHERE c.source = 'internal'
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- 定时任务：故事线建线/续接（盘中每 30 分钟）、订阅命中扫描（每 10 分钟，不耗 LLM）、
-- 热点主题榜盘中/盘后双跑（盘后 16:35 晚于板块收盘快照 16:05，盘中跑用 T-1 并标注）
INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES
    ('news_storyline',          'news-storyline',          'internal', '*/30 9-16 * * 1-5', true),
    ('news_subscription_match', 'news-subscription-match', 'internal', '*/10 * * * *',     true),
    ('news_topic_intraday',     'news-topic',              'internal', '35 11 * * 1-5',     true),
    ('news_topic_post',         'news-topic',              'internal', '35 16 * * 1-5',     true)
ON CONFLICT (task_name) DO UPDATE
SET task_type = EXCLUDED.task_type, source = EXCLUDED.source;
