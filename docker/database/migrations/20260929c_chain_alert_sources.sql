-- 产业链提醒结构化信源（用户反馈：提醒须可溯源）
-- chain_alert 增加 sources JSONB：分析任务引用的信源条目数组
-- （[{title, source, publish_date}]），由 LLM 从检索到的新闻/公告/研报中带回。
-- 幂等：ADD COLUMN IF NOT EXISTS；重放无副作用。

ALTER TABLE chain_alert ADD COLUMN IF NOT EXISTS sources JSONB;
