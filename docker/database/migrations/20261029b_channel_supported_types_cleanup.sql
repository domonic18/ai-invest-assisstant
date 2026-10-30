-- 渠道 supported_data_types 数据校正
-- 1) 20261019c 末条 UPDATE 写成 `A || B - C`：PostgreSQL 二元 `-` 优先级高于
--    `||`，实际按 `A || (B - C)` 求值，eastmoney 的 financial-report 未被移除，
--    concept-constituents 反被重复追加。本迁移按原意补齐清理。
-- 2) cls 的 news-telegraph 为早期遗留数据类型：无对应采集器、无关联行，清除。
-- 3) 全渠道数组去重（保留首次出现顺序）。
-- 幂等：重复执行无副作用。

DELETE FROM collector_channel_data_type d
USING collector_channel_config c
WHERE c.id = d.channel_id
  AND (
    (c.source = 'eastmoney' AND d.data_type = 'financial-report')
    OR (c.source = 'cls' AND d.data_type = 'news-telegraph')
  );

WITH cleaned AS (
    SELECT c2.id,
           COALESCE(
               jsonb_agg(e.value ORDER BY e.min_ord) FILTER (WHERE e.value IS NOT NULL),
               '[]'::jsonb
           ) AS arr
    FROM collector_channel_config c2
    LEFT JOIN LATERAL (
        SELECT elem.value, min(elem.ord) AS min_ord
        FROM jsonb_array_elements_text(c2.supported_data_types)
             WITH ORDINALITY AS elem(value, ord)
        WHERE NOT (c2.source = 'eastmoney' AND elem.value = 'financial-report')
          AND NOT (c2.source = 'cls' AND elem.value = 'news-telegraph')
        GROUP BY elem.value
    ) e ON TRUE
    GROUP BY c2.id
)
UPDATE collector_channel_config c
SET supported_data_types = cleaned.arr
FROM cleaned
WHERE c.id = cleaned.id
  AND c.supported_data_types IS DISTINCT FROM cleaned.arr;
