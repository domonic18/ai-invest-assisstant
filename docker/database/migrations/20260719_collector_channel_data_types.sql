-- 渠道-数据类型关联及优先级表（老库迁移，幂等可重复执行）
-- 优先级回插取 channel.id，与迁移前 resolver 的 order by id 行为等价

CREATE TABLE IF NOT EXISTS collector_channel_data_type (
    id          BIGSERIAL PRIMARY KEY,
    channel_id  BIGINT      NOT NULL REFERENCES collector_channel_config(id) ON DELETE CASCADE,
    data_type   VARCHAR(50) NOT NULL,
    priority    INTEGER     NOT NULL DEFAULT 100,
    CONSTRAINT uq_ccdt_channel_type UNIQUE (channel_id, data_type)
);

CREATE INDEX IF NOT EXISTS idx_ccdt_data_type_priority
    ON collector_channel_data_type(data_type, priority);

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT c.id, t.data_type, c.id
FROM collector_channel_config c
CROSS JOIN LATERAL jsonb_array_elements_text(c.supported_data_types) AS t(data_type)
ON CONFLICT (channel_id, data_type) DO NOTHING;
