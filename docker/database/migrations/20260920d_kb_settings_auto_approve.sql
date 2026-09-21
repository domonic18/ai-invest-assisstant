-- 20260920d: 知识点审核自动化开关——抽取管线全绿卡默认自动发布，
-- 仅确定性升级信号（时间码缺失/摘录未命中/未归章/置信度不足/case 卡）留人工审核。
ALTER TABLE kb_settings ADD COLUMN IF NOT EXISTS auto_approve_points BOOLEAN NOT NULL DEFAULT TRUE;
