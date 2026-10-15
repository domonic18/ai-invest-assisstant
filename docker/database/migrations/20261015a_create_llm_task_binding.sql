-- AI 任务级模型分配：llm_task_binding（task_key → llm_config 条目绑定）。
-- 一行 = 一个任务槽位的绑定；无行 = 该任务跟随系统默认对话模型（含其主备链）。
-- config_id 无 FK（沿用 backup_config_id 惯例）：引用有效性（存在/启用/purpose=chat）
-- 由服务层写侧校验；读侧绑定条目失效时降级默认并告警（调度可用性优先）。
-- 幂等：CREATE TABLE IF NOT EXISTS + DO 块防重加唯一约束；重放无副作用。

CREATE TABLE IF NOT EXISTS llm_task_binding (
    id          BIGSERIAL    PRIMARY KEY,
    task_key    VARCHAR(64)  NOT NULL,
    config_id   BIGINT       NOT NULL,
    updated_by  BIGINT,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT chk_llm_task_binding_task_key CHECK (char_length(task_key) > 0)
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_llm_task_binding_task_key'
    ) THEN
        ALTER TABLE llm_task_binding
            ADD CONSTRAINT uq_llm_task_binding_task_key UNIQUE (task_key);
    END IF;
END $$;
