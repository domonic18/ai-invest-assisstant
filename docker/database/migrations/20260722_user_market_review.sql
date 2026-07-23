-- 每日大盘综述多租户隔离：用户编辑副本表

CREATE TABLE IF NOT EXISTS user_market_review (
    id                BIGSERIAL PRIMARY KEY,
    user_id           BIGINT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    trade_date        DATE NOT NULL,
    overview          TEXT NOT NULL,
    emotion_analysis  TEXT NOT NULL,
    capital_analysis  TEXT NOT NULL,
    risk_advice       TEXT NOT NULL,
    model             VARCHAR(50),
    generated_at      TIMESTAMPTZ,
    base_review_id    BIGINT REFERENCES ai_analysis_result(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (user_id, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_user_market_review_user_date ON user_market_review(user_id, trade_date);
CREATE INDEX IF NOT EXISTS idx_user_market_review_trade_date ON user_market_review(trade_date);

CREATE INDEX IF NOT EXISTS idx_ai_skill_hash ON ai_analysis_result(skill_id, input_hash);

-- 每日大盘综述 16:00 定时生成任务
INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES ('market_daily_review_1600', 'market-daily-review', 'internal', '0 16 * * 1-5', true)
ON CONFLICT (task_name) DO NOTHING;
