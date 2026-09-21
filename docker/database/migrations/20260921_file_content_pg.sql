-- 20260921: 全系统去 ES——研报/财报全文入 PG，死列退役（幂等可重放）
-- file_metadata.content 存 pypdf 抽取的 PDF 全文（入库时写入 + MinIO 重抽回填），
--   GIN trgm 支撑 search_vector_kb 的 ILIKE 词面检索
-- news_document.elasticsearch_doc_id 死列退役：所有写入方一直写 NULL
-- （历史迁移 20260722_schema_refactor.sql 保留不动）
CREATE EXTENSION IF NOT EXISTS pg_trgm;

ALTER TABLE file_metadata ADD COLUMN IF NOT EXISTS content TEXT;
CREATE INDEX IF NOT EXISTS idx_file_metadata_content_trgm
  ON file_metadata USING gin (content gin_trgm_ops);
ALTER TABLE news_document DROP COLUMN IF EXISTS elasticsearch_doc_id;
