-- kb 素材显示优化：relative_path 列持久化上传时的目录结构（上传列表展示目录树）。
-- 存量 file_name ASCII 净化损坏属开发态数据修复，不进迁移库（2026-09-20 评审定约）。

ALTER TABLE kb_media ADD COLUMN IF NOT EXISTS relative_path VARCHAR(500);
