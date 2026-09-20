-- 批次 E 勾稽：审批发布先于 embedding_dirty 标志位落库的存量 published 点
-- 从未被置脏，增量索引扫描永不上料。回填置脏让下轮 kb-index 补齐投影。
-- 重放效应：再次置脏全部 published 点 → 多跑一轮增量 upsert 后自愈（安全）。
UPDATE kb_knowledge_point
SET embedding_dirty = TRUE
WHERE status = 'published' AND embedding_dirty = FALSE;
