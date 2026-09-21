-- 20260920f: 批次 J 检索去投影化——PG 单库检索列（幂等可重放）
-- 向量路：三表 embedding halfvec(2048) + HNSW(halfvec_cosine_ops)
--   （2048 维必须 halfvec：vector 类型 HNSW 上限 2000 维）
-- 词面路：point/image search_text 生成列（拼接口径 = 嵌入输入单一真相）+
--   segment 直接用 text 列，均建 GIN(gin_trgm_ops)
-- 生成列表达式只能用不可变函数（concat_ws/array_to_string 均为 STABLE），
-- 故用 CASE/COALESCE/|| 显式拼接：非空段以 \n 连接，空/NULL 段跳过——
-- 与 Python "\n".join(part for part in (...) if part) 语义逐点一致
-- 维度变更（罕见）：ALTER ... TYPE halfvec(n) + 索引重建 + 全量重嵌
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

ALTER TABLE kb_knowledge_point
  ADD COLUMN IF NOT EXISTS embedding halfvec(2048),
  ADD COLUMN IF NOT EXISTS search_text TEXT GENERATED ALWAYS AS (
    COALESCE(nullif(title, ''), '')
    || CASE WHEN nullif(title, '') IS NOT NULL AND nullif(term_definition, '') IS NOT NULL
            THEN E'\n' ELSE '' END || COALESCE(nullif(term_definition, ''), '')
    || CASE WHEN (nullif(title, '') IS NOT NULL OR nullif(term_definition, '') IS NOT NULL)
               AND nullif(body, '') IS NOT NULL
            THEN E'\n' ELSE '' END || COALESCE(nullif(body, ''), '')
    || CASE WHEN (nullif(title, '') IS NOT NULL OR nullif(term_definition, '') IS NOT NULL
                  OR nullif(body, '') IS NOT NULL) AND nullif(applicable_scene, '') IS NOT NULL
            THEN E'\n' ELSE '' END || COALESCE(nullif(applicable_scene, ''), '')
  ) STORED;

ALTER TABLE kb_transcript_segment
  ADD COLUMN IF NOT EXISTS embedding halfvec(2048);

ALTER TABLE kb_image_asset
  ADD COLUMN IF NOT EXISTS embedding halfvec(2048),
  ADD COLUMN IF NOT EXISTS search_text TEXT GENERATED ALWAYS AS (
    COALESCE(nullif(text_in_image, ''), '')
    || CASE WHEN nullif(text_in_image, '') IS NOT NULL AND nullif(caption, '') IS NOT NULL
            THEN E'\n' ELSE '' END || COALESCE(nullif(caption, ''), '')
    || CASE WHEN (nullif(text_in_image, '') IS NOT NULL OR nullif(caption, '') IS NOT NULL)
               AND nullif(vision_description, '') IS NOT NULL
            THEN E'\n' ELSE '' END || COALESCE(nullif(vision_description, ''), '')
  ) STORED;

CREATE INDEX IF NOT EXISTS idx_kb_point_embedding
  ON kb_knowledge_point USING hnsw (embedding halfvec_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_kb_point_search_text_trgm
  ON kb_knowledge_point USING gin (search_text gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_kb_segment_embedding
  ON kb_transcript_segment USING hnsw (embedding halfvec_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_kb_segment_text_trgm
  ON kb_transcript_segment USING gin (text gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_kb_image_embedding
  ON kb_image_asset USING hnsw (embedding halfvec_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_kb_image_search_text_trgm
  ON kb_image_asset USING gin (search_text gin_trgm_ops);
