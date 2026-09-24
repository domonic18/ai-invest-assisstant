-- K 线画线与 AI 智能画线（F-DRAW）数据底座：用户画线 / AI 画线两表（幂等可重复执行）。
-- 锚点一律存数据坐标 (date, price)（payload JSONB），像素坐标禁止落库；
-- 周期（period）是画线归属键的一部分，各周期画线集严格隔离。
-- 架构：docs/arch/09-kline-drawing.md §5；需求：docs/requirement/03-kline-drawing-requirement.md §5.9

-- ============================================================
-- 1. user_kline_drawing：用户画线（per-user 私有，每行一条画线）
-- ============================================================

CREATE TABLE IF NOT EXISTS user_kline_drawing (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT      NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    target_type  VARCHAR(16) NOT NULL,                 -- stock / index / sector
    target_code  VARCHAR(16) NOT NULL,                 -- 6 位代码或指数/板块代码
    period       VARCHAR(8)  NOT NULL,                 -- daily / weekly / monthly
    drawing_type VARCHAR(16) NOT NULL,                 -- trendline / ray / hline / box / text
    payload      JSONB       NOT NULL,                 -- {anchors[], direction?, text?, style{}}
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_user_kline_drawing_target_type CHECK (target_type IN ('stock', 'index', 'sector')),
    CONSTRAINT chk_user_kline_drawing_period CHECK (period IN ('daily', 'weekly', 'monthly')),
    CONSTRAINT chk_user_kline_drawing_type CHECK (drawing_type IN ('trendline', 'ray', 'hline', 'box', 'text'))
);

CREATE INDEX IF NOT EXISTS idx_user_kline_drawing_scope
    ON user_kline_drawing(user_id, target_type, target_code, period);

-- ============================================================
-- 2. ai_kline_drawing：AI 画线集（全局共享、可变工作区，
--    每标的每周期一套，drawings 数组 label 组内唯一）
-- ============================================================

CREATE TABLE IF NOT EXISTS ai_kline_drawing (
    id          BIGSERIAL PRIMARY KEY,
    target_type VARCHAR(16) NOT NULL,
    target_code VARCHAR(16) NOT NULL,
    period      VARCHAR(8)  NOT NULL,
    skill_id    VARCHAR(64) NOT NULL,                  -- 最近一次生成来源（kline-smart-drawing）
    trade_date  DATE,                                  -- 最近一次生成对应交易日（展示用）
    drawings    JSONB       NOT NULL DEFAULT '[]'::jsonb, -- [{drawingType, anchors, direction?, label, reason}]
    summary     TEXT,                                  -- 本组画线一段话说明（面板展示）
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_ai_kline_drawing UNIQUE (target_type, target_code, period),
    CONSTRAINT chk_ai_kline_drawing_target_type CHECK (target_type IN ('stock', 'index', 'sector')),
    CONSTRAINT chk_ai_kline_drawing_period CHECK (period IN ('daily', 'weekly', 'monthly'))
);
