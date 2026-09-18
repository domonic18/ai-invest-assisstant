-- ============================================================
-- F-KB 温成趋势理论知识库 数据底座
-- kb_source / kb_media / kb_transcript_segment / kb_knowledge_point /
-- kb_image_asset / kb_settings 六表
-- + llm_config.purpose 用途维度 + user_token_usage.detail 建库上下文
-- 幂等可重复执行；01-schema.sql 已同步
-- ============================================================

CREATE TABLE IF NOT EXISTS kb_source (
    id                    BIGSERIAL PRIMARY KEY,
    source_type           VARCHAR(16)  NOT NULL,                     -- course / book
    name                  VARCHAR(200) NOT NULL,
    author                VARCHAR(100),                              -- 讲师 / 作者
    description           TEXT,
    enabled               BOOLEAN      NOT NULL DEFAULT TRUE,
    chapter_tree          JSONB        NOT NULL DEFAULT '{"draft": null, "published": null}'::jsonb,
    storage_bytes         BIGINT       NOT NULL DEFAULT 0,           -- COS 登记字节数聚合
    pending_cleanup_bytes BIGINT       NOT NULL DEFAULT 0,           -- 异步清理未完成量
    deleted_at            TIMESTAMPTZ,                               -- 软删（24h 恢复窗）
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_kb_source_type CHECK (source_type IN ('course', 'book'))
);

CREATE INDEX IF NOT EXISTS idx_kb_source_active ON kb_source(deleted_at) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS kb_media (
    id               BIGSERIAL PRIMARY KEY,
    source_id        BIGINT       NOT NULL REFERENCES kb_source(id) ON DELETE CASCADE,
    media_kind       VARCHAR(8)   NOT NULL,                          -- video / audio / book
    episode_no       INT,                                            -- 课程集号（书为 NULL）
    title            VARCHAR(300) NOT NULL,
    file_name        VARCHAR(500) NOT NULL,
    cos_key          VARCHAR(500) NOT NULL,
    file_size        BIGINT       NOT NULL DEFAULT 0,
    file_hash        VARCHAR(64)  NOT NULL,                          -- md5（uploaded 核对与去重）
    duration_seconds INT,                                            -- 课程素材时长（秒）
    page_count       INT,                                            -- 书册页数
    process_status   VARCHAR(16)  NOT NULL DEFAULT 'uploaded',
    process_error    VARCHAR(1000),
    process_meta     JSONB        NOT NULL DEFAULT '{}'::jsonb,      -- 用量对账：provider/model/audio_seconds/est_cost…
    extracted_at     TIMESTAMPTZ,                                    -- 知识抽取完成时刻（抽取任务幂等键）
    edited_at        TIMESTAMPTZ,                                    -- 文稿人工编辑时刻（脏传播源）
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_kb_media_source_hash UNIQUE (source_id, file_hash),
    CONSTRAINT chk_kb_media_kind CHECK (media_kind IN ('video', 'audio', 'book')),
    CONSTRAINT chk_kb_media_status CHECK (process_status IN
        ('uploaded', 'awaiting_cost', 'queued', 'processing', 'done', 'failed'))
);

-- 集号唯一仅约束课程（书的 episode_no 为 NULL，PG 唯一约束不冲突多个 NULL）
CREATE UNIQUE INDEX IF NOT EXISTS uq_kb_media_source_episode
    ON kb_media(source_id, episode_no) WHERE episode_no IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_kb_media_source_status ON kb_media(source_id, process_status);

CREATE TABLE IF NOT EXISTS kb_transcript_segment (
    id              BIGSERIAL PRIMARY KEY,
    media_id        BIGINT      NOT NULL REFERENCES kb_media(id) ON DELETE CASCADE,
    source_id       BIGINT      NOT NULL REFERENCES kb_source(id) ON DELETE CASCADE,  -- 冗余，脏扫描按源过滤
    seq_no          INT         NOT NULL,
    text            TEXT        NOT NULL,
    start_ms        BIGINT,                                               -- 课程：句级起（毫秒）
    end_ms          BIGINT,
    page_start      INT,                                                  -- 书：页区间
    page_end        INT,
    embedding_dirty BOOLEAN     NOT NULL DEFAULT TRUE,                    -- 索引任务增量拾取
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_kb_segment_media_seq UNIQUE (media_id, seq_no)
);

CREATE INDEX IF NOT EXISTS idx_kb_segment_dirty ON kb_transcript_segment(embedding_dirty) WHERE embedding_dirty;
CREATE INDEX IF NOT EXISTS idx_kb_segment_source_dirty ON kb_transcript_segment(source_id, embedding_dirty);

CREATE TABLE IF NOT EXISTS kb_knowledge_point (
    id               BIGSERIAL PRIMARY KEY,
    source_id        BIGINT       NOT NULL REFERENCES kb_source(id) ON DELETE CASCADE,
    media_id         BIGINT       NOT NULL REFERENCES kb_media(id) ON DELETE CASCADE,
    point_type       VARCHAR(16)  NOT NULL,                         -- concept/theorem/method/discipline/case
    title            VARCHAR(300) NOT NULL,
    body             TEXT         NOT NULL,                         -- 正文（保留讲师表述）
    term_definition  TEXT,
    applicable_scene TEXT,
    excerpt          TEXT         NOT NULL,                         -- 原文摘录（审核后不可改）
    start_ms         BIGINT,                                        -- 课程定位（句级起止）
    end_ms           BIGINT,
    page_start       INT,                                           -- 书定位（页区间）
    page_end         INT,
    related_ids      JSONB        NOT NULL DEFAULT '[]'::jsonb,     -- 关联知识点 id
    chapter_path     JSONB        NOT NULL DEFAULT '[]'::jsonb,     -- 发布树节点 id 串
    status           VARCHAR(16)  NOT NULL DEFAULT 'draft',
    needs_review     BOOLEAN      NOT NULL DEFAULT FALSE,           -- excerpt 校验未过显式标记
    review_note      VARCHAR(1000),
    reviewed_by      BIGINT REFERENCES "user"(id) ON DELETE SET NULL,
    reviewed_at      TIMESTAMPTZ,
    embedding_dirty  BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_kb_point_type CHECK (point_type IN ('concept', 'theorem', 'method', 'discipline', 'case')),
    CONSTRAINT chk_kb_point_status CHECK (status IN ('draft', 'published', 'rejected'))
);

CREATE INDEX IF NOT EXISTS idx_kb_point_source_status ON kb_knowledge_point(source_id, status);
CREATE INDEX IF NOT EXISTS idx_kb_point_dirty ON kb_knowledge_point(embedding_dirty) WHERE embedding_dirty;

CREATE TABLE IF NOT EXISTS kb_image_asset (
    id                 BIGSERIAL PRIMARY KEY,
    media_id           BIGINT       NOT NULL REFERENCES kb_media(id) ON DELETE CASCADE,
    source_id          BIGINT       NOT NULL REFERENCES kb_source(id) ON DELETE CASCADE,
    page_no            INT          NOT NULL,
    bbox               JSONB,                                        -- 页内位置（可空）
    cos_key            VARCHAR(500) NOT NULL,                        -- 原图
    thumb_cos_key      VARCHAR(500),                                 -- 缩略图
    text_in_image      TEXT,                                         -- 图内文字（VLM 识别）
    caption            TEXT,                                         -- 图注推断
    vision_description TEXT,                                         -- 视觉描述
    describe_status    VARCHAR(16)  NOT NULL DEFAULT 'pending',
    embedding_dirty    BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_kb_image_describe_status CHECK (describe_status IN ('pending', 'processing', 'done', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_kb_image_source_dirty ON kb_image_asset(source_id, embedding_dirty);

CREATE TABLE IF NOT EXISTS kb_settings (
    id                  BIGSERIAL PRIMARY KEY CHECK (id = 1),
    hotwords            JSONB       NOT NULL DEFAULT '[]'::jsonb,    -- 金融热词表（注入清洗 prompt）
    segment_max_seconds INT         NOT NULL DEFAULT 30,
    asr_concurrency     INT         NOT NULL DEFAULT 2,
    top_k               INT         NOT NULL DEFAULT 8,
    unit_prices         JSONB       NOT NULL DEFAULT '{}'::jsonb,    -- {asrPerHour, vlmPerImage} 参考单价
    embedding_config_id BIGINT REFERENCES llm_config(id) ON DELETE SET NULL,
    clean_model_id      BIGINT REFERENCES llm_config(id) ON DELETE SET NULL,
    extract_model_id    BIGINT REFERENCES llm_config(id) ON DELETE SET NULL,
    vision_model_id     BIGINT REFERENCES llm_config(id) ON DELETE SET NULL,
    authorized_user_ids JSONB       NOT NULL DEFAULT '[]'::jsonb,    -- 知识库授权白名单（admin 隐含）
    updated_by          BIGINT REFERENCES "user"(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_kb_settings_segment CHECK (segment_max_seconds BETWEEN 5 AND 120),
    CONSTRAINT chk_kb_settings_asr_concurrency CHECK (asr_concurrency BETWEEN 1 AND 8),
    CONSTRAINT chk_kb_settings_top_k CHECK (top_k BETWEEN 1 AND 50)
);

-- 缺省设置行（管理端「知识库设置」维护）
INSERT INTO kb_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

-- ------------------------------------------------------------
-- 既有表扩展：llm_config 用途维度（管线模型角色绑定的单一真相源）
-- ------------------------------------------------------------

ALTER TABLE llm_config ADD COLUMN IF NOT EXISTS purpose VARCHAR(16) NOT NULL DEFAULT 'chat';
ALTER TABLE llm_config DROP CONSTRAINT IF EXISTS chk_llm_config_purpose;
ALTER TABLE llm_config ADD CONSTRAINT chk_llm_config_purpose
    CHECK (purpose IN ('chat', 'embedding', 'vision'));

-- ------------------------------------------------------------
-- 既有表扩展：user_token_usage 建库上下文与 kb_* 特征
-- ------------------------------------------------------------

ALTER TABLE user_token_usage ADD COLUMN IF NOT EXISTS detail JSONB;

ALTER TABLE user_token_usage DROP CONSTRAINT IF EXISTS chk_user_token_usage_feature;
ALTER TABLE user_token_usage ADD CONSTRAINT chk_user_token_usage_feature
    CHECK (feature IN ('assistant', 'page', 'api_key', 'system',
                       'kb_clean', 'kb_extract', 'kb_vision', 'kb_embed'));
