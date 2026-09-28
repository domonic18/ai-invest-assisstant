-- 迭代 3 资讯中心：资讯 AI 重要度分级独立表 + 定时任务（幂等可重复执行）
-- news_ai_score：跨源通用标注表（电报/新闻/公告/推文/视频共用），
-- (source, item_id) 挂到各源自有表的业务主键，不改动任何源表结构

CREATE TABLE IF NOT EXISTS news_ai_score (
    source       VARCHAR(32)  NOT NULL,               -- 来源标识（cls_telegraph / sina_news / ...）
    item_id      VARCHAR(64)  NOT NULL,               -- 源表业务主键（电报=cls_msg_id）
    score        INT          NOT NULL,               -- AI 重要度 0-100
    score_detail JSONB,                               -- {reason, factors}
    scored_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    PRIMARY KEY (source, item_id),
    CONSTRAINT chk_news_ai_score_value CHECK (score >= 0 AND score <= 100)
);

-- 重点视图（迭代 4）跨源取高分项预埋
CREATE INDEX IF NOT EXISTS idx_news_ai_score_score ON news_ai_score(score DESC);

-- internal 渠道补登 news-score 数据类型（渠道解析按任务名匹配 collector_channel_data_type，
-- 缺此关联行时 run_task 解析不到渠道，任务以 SKIPPED「没有启用任何可用的采集渠道」结束）
UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["news-score"]'::jsonb
WHERE source = 'internal'
  AND NOT supported_data_types @> '["news-score"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'news-score', 1
FROM collector_channel_config
WHERE source = 'internal'
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- AI 分级定时任务：每 5 分钟批量评分未分级资讯（internal 渠道直调服务层）
INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES
    ('news_ai_score', 'news-score', 'internal', '*/5 * * * *', true)
ON CONFLICT (task_name) DO UPDATE
SET task_type = EXCLUDED.task_type, source = EXCLUDED.source;
