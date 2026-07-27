-- 股票-概念映射表（同花顺概念成分股）
CREATE TABLE IF NOT EXISTS mapping_stock_concept (
    id            BIGSERIAL PRIMARY KEY,
    stock_code    VARCHAR(10)  NOT NULL,
    concept_code  VARCHAR(20)  NOT NULL,
    concept_name  VARCHAR(100) NOT NULL,
    source        VARCHAR(50)  DEFAULT 'ths' NOT NULL,
    updated_at    TIMESTAMPTZ  DEFAULT NOW(),

    CONSTRAINT uq_mapping_stock_concept_stock_concept
        UNIQUE (stock_code, concept_code)
);

CREATE INDEX IF NOT EXISTS idx_mapping_stock_concept_stock_code
    ON mapping_stock_concept(stock_code);
CREATE INDEX IF NOT EXISTS idx_mapping_stock_concept_concept_code
    ON mapping_stock_concept(concept_code);

-- 防御性补齐 ths 渠道的 concept-constituents 数据类型
UPDATE collector_channel_config
SET supported_data_types = supported_data_types || '["concept-constituents"]'::jsonb
WHERE source = 'ths'
  AND NOT supported_data_types @> '["concept-constituents"]'::jsonb;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'concept-constituents', 1
FROM collector_channel_config
WHERE source = 'ths'
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- 每日凌晨全量更新概念成分股
INSERT INTO collector_task (task_name, task_type, source, schedule, is_active)
VALUES ('ths_concept_constituents', 'concept-constituents', 'ths', '0 2 * * *', true)
ON CONFLICT (task_name) DO NOTHING;
