-- LLM 主备下沉到选择点（expand）：备用引用从 llm_config 条目迁移到各消费侧槽位。
-- llm_task_binding 加 backup_config_id；kb_settings 四角色与 trading_agent 同构加备列。
-- backfill 自 llm_config 旧字段（is_default/backup_config_id），旧列本批不删（保回滚，
-- contract 删列放下一个发布周期）。新增槽位 assistant_chat（对话系统出口，原 is_default
-- 的显式化）与 decision（判断模型，原 purpose 扫描 + 条目备用的显式化）。
-- 幂等：ADD COLUMN IF NOT EXISTS / INSERT ON CONFLICT DO NOTHING / UPDATE 带 IS NULL 守卫。

ALTER TABLE llm_task_binding ADD COLUMN IF NOT EXISTS backup_config_id BIGINT;

ALTER TABLE kb_settings ADD COLUMN IF NOT EXISTS embedding_backup_id BIGINT;
ALTER TABLE kb_settings ADD COLUMN IF NOT EXISTS clean_backup_id BIGINT;
ALTER TABLE kb_settings ADD COLUMN IF NOT EXISTS extract_backup_id BIGINT;
ALTER TABLE kb_settings ADD COLUMN IF NOT EXISTS vision_backup_id BIGINT;

ALTER TABLE trading_agent ADD COLUMN IF NOT EXISTS llm_backup_config_id BIGINT;

-- 存量绑定行：备位 = 所绑主条目的旧条目级备用
UPDATE llm_task_binding b
SET backup_config_id = c.backup_config_id
FROM llm_config c
WHERE b.config_id = c.id
  AND b.backup_config_id IS NULL
  AND c.backup_config_id IS NOT NULL;

-- chat 槽位缺行兜底（含新增 assistant_chat）：primary = 当前系统默认条目
INSERT INTO llm_task_binding (task_key, config_id, backup_config_id)
SELECT slot.key, d.id, d.backup_config_id
FROM (
    VALUES ('assistant_chat'), ('news_score'), ('social_sentiment'),
           ('news_storyline'), ('news_topic'), ('market_daily_review'),
           ('sector_anomaly'), ('stock_anomaly'), ('stock_daily_analysis'),
           ('limit_up_review'), ('chain_refresh')
) AS slot(key)
CROSS JOIN LATERAL (
    SELECT id, backup_config_id
    FROM llm_config
    WHERE is_default = TRUE AND is_active = TRUE
    ORDER BY id
    LIMIT 1
) d
ON CONFLICT (task_key) DO NOTHING;

-- decision 槽位：primary = 首个启用的判断模型条目
INSERT INTO llm_task_binding (task_key, config_id, backup_config_id)
SELECT 'decision', c.id, c.backup_config_id
FROM (
    SELECT id, backup_config_id
    FROM llm_config
    WHERE purpose = 'decision' AND is_active = TRUE
    ORDER BY id
    LIMIT 1
) c
ON CONFLICT (task_key) DO NOTHING;

-- kb_settings 四角色备位 = 各自主条目的旧条目级备用
UPDATE kb_settings s
SET embedding_backup_id = c.backup_config_id
FROM llm_config c
WHERE s.embedding_config_id = c.id
  AND s.embedding_backup_id IS NULL
  AND c.backup_config_id IS NOT NULL;

UPDATE kb_settings s
SET clean_backup_id = c.backup_config_id
FROM llm_config c
WHERE s.clean_model_id = c.id
  AND s.clean_backup_id IS NULL
  AND c.backup_config_id IS NOT NULL;

UPDATE kb_settings s
SET extract_backup_id = c.backup_config_id
FROM llm_config c
WHERE s.extract_model_id = c.id
  AND s.extract_backup_id IS NULL
  AND c.backup_config_id IS NOT NULL;

UPDATE kb_settings s
SET vision_backup_id = c.backup_config_id
FROM llm_config c
WHERE s.vision_model_id = c.id
  AND s.vision_backup_id IS NULL
  AND c.backup_config_id IS NOT NULL;

-- trading_agent 备位 = 各自绑定主条目的旧条目级备用
UPDATE trading_agent t
SET llm_backup_config_id = c.backup_config_id
FROM llm_config c
WHERE t.llm_config_id = c.id
  AND t.llm_backup_config_id IS NULL
  AND c.backup_config_id IS NOT NULL;
