-- file_metadata 增加 summary 列：财报/文件类 AI 摘要共享缓存（懒生成写回）
ALTER TABLE file_metadata ADD COLUMN IF NOT EXISTS summary TEXT;
