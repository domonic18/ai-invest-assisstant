-- 20260920e: 章节浏览清单端点（GET /kb/sources/{id}/points）的 GIN 支撑
-- chapter_path @> containment 前缀查询走 jsonb_path_ops 索引（幂等可重放）
CREATE INDEX IF NOT EXISTS idx_kb_point_chapter_path
  ON kb_knowledge_point USING GIN (chapter_path jsonb_path_ops);
