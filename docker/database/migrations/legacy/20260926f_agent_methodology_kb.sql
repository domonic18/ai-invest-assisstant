-- 交易 Agent 方法论基座接入 KB（方案 A，2026-09-26 定版；docs/plan/paper-trading-plan.md §10.2/§12）。
-- 温程《趋势理论》整套方法论以 KB 为单一真相源（kb_knowledge_point 直读，
-- 不复制进 agent_memory）：纪律条目每日全量注入（硬约束不参与检索）+ 发布
-- 目录树做体系总纲 + 当日盘面文本 RRF 检索相关方法/定理/概念/案例。
-- agent_memory 回归本职只装迭代经验（复盘沉淀 + 手动沉淀）：
-- 20260926e 引入的 13 条方法论种子随本迁移下架（按 title 精确匹配，幂等）。
-- 幂等，可全量重放。

-- 1. trading_agent_config 增加方法论知识源绑定（NULL = 未启用方法论基座注入）
ALTER TABLE trading_agent_config
    ADD COLUMN IF NOT EXISTS methodology_source_id BIGINT;

COMMENT ON COLUMN trading_agent_config.methodology_source_id IS
    '方法论知识源（kb_source.id，温程《趋势理论》）；NULL = 未启用方法论基座注入';

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_trading_agent_config_methodology_source'
    ) THEN
        ALTER TABLE trading_agent_config
            ADD CONSTRAINT fk_trading_agent_config_methodology_source
            FOREIGN KEY (methodology_source_id) REFERENCES kb_source (id) ON DELETE SET NULL;
    END IF;
END $$;

-- 缺省绑定温程《趋势理论》：仅当该知识源已存在时生效（全新环境 kb_source 为空，
-- 保持 NULL 降级，由管理端后续指定），避免 FK 违规
UPDATE trading_agent_config c
SET methodology_source_id = 1
WHERE c.id = 1
  AND c.methodology_source_id IS NULL
  AND EXISTS (SELECT 1 FROM kb_source s WHERE s.id = 1);

-- 2. 下架 agent_memory 方法论种子（经验层从空集起步；批次 9 复盘沉淀重新填充）
DELETE FROM agent_memory
WHERE source = 'manual'
  AND title IN (
      '选股本质是选板块：无板块效应不参与',
      '不碰后排被动上涨个股',
      '位置优先：M60 之下的个股不参与',
      '横盘不埋伏，等放量涨停启动',
      '三元一催化是开仓总开关',
      '机会只在拐点：无板块联动期坚决空仓',
      '跟随市场：只做市场选出的最强龙头',
      '见顶信号：高位巨量巨震大换手即线上卖点',
      '启动是分歧转一致，见顶是一致转分歧',
      '分时缩量诱多是常用分时卖点',
      '不求卖在最高点，抓最安全一段',
      '赢多胜小亏：仓位从轻靠时间积累',
      'M60 红包：前期龙头回落 M60 的套利模型'
  );
