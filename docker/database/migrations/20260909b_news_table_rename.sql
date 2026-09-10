-- 资讯表名规范化：news_announcement→news_document、calendar_event→news_calendar_event（幂等可重复执行）
-- news_announcement 实为 doc_type(news/announcement/research/financial_report) 混合的通用资讯文档表；
-- calendar_event（财联社投资日历）归 news_ 家族。约束/索引名同步归位 pk_/uq_/chk_/idx_<table>_* 约定。

-- 1. 表重命名（已改名则 no-op）
ALTER TABLE IF EXISTS news_announcement RENAME TO news_document;
ALTER TABLE IF EXISTS calendar_event RENAME TO news_calendar_event;

-- 2. 约束名归位（PG 不支持 RENAME CONSTRAINT IF EXISTS，用 DO 块判存）
DO $$
DECLARE
    renames CONSTANT TEXT[][] := ARRAY[
        ['news_document', 'news_announcement_pkey', 'pk_news_document'],
        ['news_document', 'news_announcement_source_url_key', 'uq_news_document_source_url'],
        ['news_document', 'news_announcement_doc_type_check', 'chk_news_document_doc_type'],
        ['news_calendar_event', 'calendar_event_pkey', 'pk_news_calendar_event'],
        ['news_calendar_event', 'uq_calendar_event_source_hash', 'uq_news_calendar_event_source_hash'],
        ['news_calendar_event', 'chk_calendar_event_category', 'chk_news_calendar_event_category']
    ];
    r TEXT[];
BEGIN
    FOREACH r SLICE 1 IN ARRAY renames LOOP
        IF EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = r[2] AND conrelid = r[1]::regclass
        ) THEN
            EXECUTE format('ALTER TABLE %I RENAME CONSTRAINT %I TO %I', r[1], r[2], r[3]);
        END IF;
    END LOOP;
END $$;

-- 3. 索引名归位（pkey/uq 的底层索引随约束自动改名，这里处理独立索引）
ALTER INDEX IF EXISTS idx_news_code_date RENAME TO idx_news_document_code_date;
ALTER INDEX IF EXISTS idx_news_doc_type RENAME TO idx_news_document_doc_type;
ALTER INDEX IF EXISTS idx_news_publish_date RENAME TO idx_news_document_publish_date;
ALTER INDEX IF EXISTS idx_calendar_event_time RENAME TO idx_news_calendar_event_time;
ALTER INDEX IF EXISTS idx_calendar_event_category_time RENAME TO idx_news_calendar_event_category_time;
