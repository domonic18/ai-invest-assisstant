-- ============================================================
-- F-SOC 社媒大 V 情绪追踪（一期）数据底座
-- social_account / social_post / social_sentiment / asr_channel_config 四表
-- 幂等可重复执行；01-schema.sql 已同步
-- ============================================================

CREATE TABLE IF NOT EXISTS social_account (
    id                    BIGSERIAL PRIMARY KEY,
    platform              VARCHAR(16)  NOT NULL,
    sec_uid               VARCHAR(64)  NOT NULL,                   -- 平台内唯一标识（抖音 sec_user_id）
    alias                 VARCHAR(64)  NOT NULL,                   -- 展示别名
    category              VARCHAR(32)  NOT NULL DEFAULT 'finance_kol',  -- macro_policy / finance_kol / industry
    remark                VARCHAR(500),
    poll_interval_minutes INT          NOT NULL DEFAULT 60,
    is_active             BOOLEAN      NOT NULL DEFAULT true,
    last_collected_at     TIMESTAMPTZ,
    last_post_at          TIMESTAMPTZ,
    last_error            VARCHAR(1000),                            -- 渠道侧账号失效诊断提示，不阻断采集
    last_error_at         TIMESTAMPTZ,
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_social_account_platform_sec_uid UNIQUE (platform, sec_uid),
    CONSTRAINT chk_social_account_platform CHECK (platform IN ('douyin')),
    CONSTRAINT chk_social_account_poll_interval CHECK (poll_interval_minutes >= 5)
);

CREATE INDEX IF NOT EXISTS idx_social_account_active ON social_account(is_active);

CREATE TABLE IF NOT EXISTS social_post (
    id                BIGSERIAL PRIMARY KEY,
    account_id        BIGINT       NOT NULL REFERENCES social_account(id) ON DELETE CASCADE,
    platform          VARCHAR(16)  NOT NULL,
    video_id          VARCHAR(64)  NOT NULL,                       -- 平台内容唯一 ID（aweme_id）
    title             VARCHAR(500),
    caption           TEXT,                                        -- 完整文案（desc）
    topic_tags        JSONB        NOT NULL DEFAULT '[]'::jsonb,   -- 话题标签（去 #）
    cover_url         TEXT,
    duration_seconds  INT,
    published_at      TIMESTAMPTZ  NOT NULL,                       -- 发布时刻（aware UTC）
    digg_count        BIGINT,
    comment_count     BIGINT,
    share_count       BIGINT,
    transcript_status VARCHAR(16)  NOT NULL DEFAULT 'ok',          -- 采集时刻即定；音频获取失败降级 missing
    transcript_text   TEXT,                                        -- 临时文稿缓存，判后即清，任何 API 永不透出
    transcript_meta   JSONB,                                       -- ASR 用量对账：音频时长/字符数/provider
    judged_at         TIMESTAMPTZ,                                 -- NULL=待判（判断幂等键）
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_social_post_platform_video UNIQUE (platform, video_id),
    CONSTRAINT chk_social_post_transcript_status CHECK (transcript_status IN ('ok', 'missing'))
);

CREATE INDEX IF NOT EXISTS idx_social_post_published ON social_post(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_social_post_account_published ON social_post(account_id, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_social_post_pending ON social_post(judged_at) WHERE judged_at IS NULL;

CREATE TABLE IF NOT EXISTS social_sentiment (
    id             BIGSERIAL PRIMARY KEY,
    post_id        BIGINT       NOT NULL REFERENCES social_post(id) ON DELETE CASCADE,
    is_relevant    BOOLEAN      NOT NULL,                         -- 无关内容（生活/广告）不入视图
    stance         VARCHAR(16)  NOT NULL,
    confidence     REAL         NOT NULL,
    core_arguments JSONB        NOT NULL DEFAULT '[]'::jsonb,      -- 一句话论点数组
    targets        JSONB        NOT NULL DEFAULT '[]'::jsonb,      -- [{target_type, name, code?}]
    summary        VARCHAR(1000) NOT NULL,
    model_name     VARCHAR(100) NOT NULL,                          -- 判断对账/审计
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_social_sentiment_post UNIQUE (post_id),
    CONSTRAINT chk_social_sentiment_stance CHECK (stance IN ('bullish', 'bearish', 'neutral')),
    CONSTRAINT chk_social_sentiment_confidence CHECK (confidence >= 0 AND confidence <= 1)
);

CREATE INDEX IF NOT EXISTS idx_social_sentiment_created ON social_sentiment(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_social_sentiment_stance_created ON social_sentiment(stance, created_at DESC);

-- ASR 转写服务渠道配置（单行表，见 F-SOC-03；04 知识库后置排期时直接复用同一设施）
CREATE TABLE IF NOT EXISTS asr_channel_config (
    id                BIGSERIAL PRIMARY KEY CHECK (id = 1),
    provider          VARCHAR(32)  NOT NULL DEFAULT 'minimax',
    base_url          VARCHAR(200) NOT NULL DEFAULT 'https://api.minimaxi.com',
    model             VARCHAR(64)  NOT NULL DEFAULT 'asr-1.0',
    api_key_encrypted TEXT,                                        -- Fernet 认证加密
    api_key_masked    VARCHAR(64),                                 -- 冗余脱敏串
    extra             JSONB        NOT NULL DEFAULT '{}'::jsonb,   -- 协议附加参数（timestamp_level/stream）
    hotwords          JSONB        NOT NULL DEFAULT '[]'::jsonb,   -- 财经热词表（注入判断 prompt）
    max_audio_seconds INT          NOT NULL DEFAULT 600,           -- 单条音频时长上限截断
    enabled           BOOLEAN      NOT NULL DEFAULT false,
    updated_by        BIGINT REFERENCES "user"(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- 缺省配置行（管理端「ASR 配置」维护；enabled 默认关，配好密钥再开）
INSERT INTO asr_channel_config (id, provider, base_url, model)
VALUES (1, 'minimax', 'https://api.minimaxi.com', 'asr-1.0')
ON CONFLICT (id) DO NOTHING;
