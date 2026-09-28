-- AI 复盘内容分区可扩展化：user_market_review 改为 sections JSONB 单列（幂等可重复执行）
-- 分区键由 prompt YAML 声明驱动，新增分析维度无需改表；旧 4 列数据回填后删除

ALTER TABLE user_market_review ADD COLUMN IF NOT EXISTS sections JSONB NOT NULL DEFAULT '{}';

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_market_review' AND column_name = 'overview'
    ) THEN
        UPDATE user_market_review
        SET sections = jsonb_strip_nulls(jsonb_build_object(
            'overview', overview,
            'capital_analysis', capital_analysis,
            'emotion_analysis', emotion_analysis,
            'risk_advice', risk_advice
        ))
        WHERE sections = '{}'::jsonb;

        ALTER TABLE user_market_review
            DROP COLUMN overview,
            DROP COLUMN capital_analysis,
            DROP COLUMN emotion_analysis,
            DROP COLUMN risk_advice;
    END IF;
END $$;
