-- F-SOC 两阶段落库：listing 阶段 shell 行以 transcript_status='pending' 即时入库，
-- 阶段二逐条转写回写为 'ok'/'missing'。白名单同步扩展；存量行均为 ok/missing，重挂校验直接通过。

ALTER TABLE social_post DROP CONSTRAINT IF EXISTS chk_social_post_transcript_status;

ALTER TABLE social_post
    ADD CONSTRAINT chk_social_post_transcript_status
    CHECK (transcript_status IN ('ok', 'missing', 'pending'));
