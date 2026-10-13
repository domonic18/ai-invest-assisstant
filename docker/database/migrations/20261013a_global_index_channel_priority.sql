-- global-index 实时链渠道优先级调整：
--   tushare us_tycr 为日频全量历史接口（限额 1 次/小时），30 分钟级实时任务
--   撞限额产生持续报错；yahoo 已承接 DXY（DX-Y.NYB）等代码回填，提前到第二位。
--   调整后 fallback 顺序：eastmoney → yahoo → mof → tushare（原 priority 同为 1
--   时按 channel id 排序，实际为 eastmoney → tushare → yahoo → mof）。
--   tushare_us_yield_daily / mof_jpy_yield_daily 有独立调度行（preferred_source
--   置首），不受本调整影响。
-- 幂等：UPDATE 为确定性赋值，重放结果一致。

UPDATE collector_channel_data_type d
SET priority = v.priority
FROM (
    VALUES
        ('eastmoney', 1),
        ('yahoo', 2),
        ('mof', 3),
        ('tushare', 4)
) AS v(source, priority)
WHERE d.data_type = 'global-index'
  AND d.channel_id = (SELECT id FROM collector_channel_config WHERE source = v.source);
