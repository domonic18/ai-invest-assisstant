-- kb_media 哈希去重改为部分唯一索引（仅存活行）：
-- 代码语义（media_repository 冲突查询过滤 deleted_at IS NULL）是软删行不占哈希位，
-- 24h 恢复窗内同内容重传应建新行；原表级 UNIQUE 约束覆盖软删行，重传撞键 500。
ALTER TABLE kb_media DROP CONSTRAINT IF EXISTS uq_kb_media_source_hash;

CREATE UNIQUE INDEX IF NOT EXISTS uq_kb_media_source_hash
    ON kb_media(source_id, file_hash) WHERE deleted_at IS NULL;
