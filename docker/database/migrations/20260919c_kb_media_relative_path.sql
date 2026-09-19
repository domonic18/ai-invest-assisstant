-- kb 素材显示优化：
-- 1) relative_path 列持久化上传时的目录结构（上传列表展示目录树）；
-- 2) 存量 file_name 曾被 ASCII 净化损坏（中文段被替换为 _），用 title + 扩展名回填。

ALTER TABLE kb_media ADD COLUMN IF NOT EXISTS relative_path VARCHAR(500);

UPDATE kb_media
SET file_name = title || '.' || split_part(file_name, '.', -1)
WHERE title IS NOT NULL AND title <> ''
  AND position('.' IN file_name) > 0
  AND file_name <> title || '.' || split_part(file_name, '.', -1);
