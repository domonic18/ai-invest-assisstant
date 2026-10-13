-- 腾讯财经渠道注册：个股分钟线盘中主渠道（ifzq mkline m1，2026-10-13 拍板）。
-- 新浪降为盘后校正备选（首根 bar 盘后修订前科，不宜盘中）；tushare stk_mins
-- 备用不启用（当前积分限频 1 次/小时，腾讯不可用时再积分升档注册）。

INSERT INTO collector_channel_config (source, name, base_url, is_enabled, supported_data_types)
VALUES ('tencent', '腾讯财经', 'https://ifzq.gtimg.cn', true, '["stock-minute"]'::jsonb)
ON CONFLICT (source) DO NOTHING;

INSERT INTO collector_channel_data_type (channel_id, data_type, priority)
SELECT id, 'stock-minute', 1
FROM collector_channel_config
WHERE source = 'tencent'
ON CONFLICT (channel_id, data_type) DO NOTHING;

-- 新浪 stock-minute 降至备选优先级（渠道故障 fallback 用）
UPDATE collector_channel_data_type d
SET priority = 2
FROM collector_channel_config c
WHERE d.channel_id = c.id
  AND c.source = 'sina'
  AND d.data_type = 'stock-minute';

-- 盘中调度：交易时段每分钟（与 index-minute 同节奏；午休/盘前空转幂等无害），
-- 缺省范围 = 涨停池 ∪ 自选股 ∪ 当日计划标的（stock_minute_base.fetch_default_codes）
INSERT INTO collector_task (task_name, task_type, source, remark, schedule, is_active, trade_day_only)
VALUES (
    'tencent_stock_minute_intraday',
    'stock-minute',
    'tencent',
    '盘中分钟线：交易 Agent 分时输入 + 前端分时展示',
    '* 9-15 * * 1-5',
    true,
    true
)
ON CONFLICT (task_name) DO NOTHING;
