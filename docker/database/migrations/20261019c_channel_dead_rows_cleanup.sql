-- 渠道-数据类型行校正：删死行 + 修复 concept-constituents 唯一渠道行错配
-- 1) 两行死行无对应注册 collector，registry 每次解析白试一轮并记 fallback
--    日志，且误导管理后台以为有备源：
--      kline|ths                  spec 有意删除的旧渠道（勿恢复）
--      financial-report|eastmoney 财报任务仅 cninfo 渠道
-- 2) concept-constituents 唯一行挂在 ths 名下，但 collector 注册在
--    eastmoney：任务自上线从未成功（生产 collector_log 全 failed，
--    mapping_stock_concept 0 行）。删错配行、在 eastmoney 名下补正确行。
-- 需同步修剪 DEFAULT_CHANNELS 声明（channels.py），否则应用启动种子逻辑
-- 会把删除的组合重新种回；渠道行 supported_data_types JSONB 数组一并清理。

DELETE FROM collector_channel_data_type d
USING collector_channel_config c
WHERE c.id = d.channel_id
  AND (
    (c.source = 'ths' AND d.data_type IN ('kline', 'concept-constituents'))
    OR (c.source = 'eastmoney' AND d.data_type = 'financial-report')
  );

-- concept-constituents 补 eastmoney 正确行（eastmoney 在 DEFAULT_CHANNELS
-- 声明序 = 2，与种子优先级口径一致）
INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT c.id, 'concept-constituents', 2
FROM collector_channel_config c
WHERE c.source = 'eastmoney'
ON CONFLICT (channel_id, data_type) DO UPDATE SET priority = 2;

UPDATE collector_channel_config
SET supported_data_types = supported_data_types - ARRAY[
    'kline', 'concept-constituents'
]::text[]
WHERE source = 'ths';

UPDATE collector_channel_config
SET supported_data_types = supported_data_types
    || '["concept-constituents"]'::jsonb
    - ARRAY['financial-report']::text[]
WHERE source = 'eastmoney';
