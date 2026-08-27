-- Collector Celery migration
-- Adds Celery task tracking, per-task queue override, and dead-letter table.

BEGIN;

ALTER TABLE collector_log
    ADD COLUMN IF NOT EXISTS celery_task_id VARCHAR(64) NULL,
    ADD CONSTRAINT uq_collector_log_celery_task_id UNIQUE (celery_task_id);

CREATE INDEX IF NOT EXISTS idx_collector_log_celery_task_id ON collector_log(celery_task_id);
CREATE INDEX IF NOT EXISTS idx_collector_log_status_started_at ON collector_log(status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_collector_log_task_name ON collector_log(task_name);

ALTER TABLE collector_task
    ADD COLUMN IF NOT EXISTS queue VARCHAR(20) NULL;

CREATE INDEX IF NOT EXISTS idx_collector_task_active_schedule ON collector_task(is_active, schedule) WHERE is_active = TRUE;

CREATE TABLE IF NOT EXISTS collector_dead_letter (
    id SERIAL PRIMARY KEY,
    task_name VARCHAR(100) NOT NULL,
    source VARCHAR(50) NULL,
    payload JSONB NOT NULL,
    celery_task_id VARCHAR(64) NULL,
    collector_log_id INT NULL,
    error_msg TEXT NULL,
    retry_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_collector_dead_letter_task_name ON collector_dead_letter(task_name);
CREATE INDEX IF NOT EXISTS idx_collector_dead_letter_created_at ON collector_dead_letter(created_at DESC);

COMMIT;
