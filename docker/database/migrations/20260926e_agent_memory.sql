-- 交易 Agent 经验沉淀底座 + 温程方法论纪律种子（docs/plan/paper-trading-plan.md §12.1）。
-- agent_memory = Agent 自有记忆（不经 KB）：active 条目由每日计划生成全量注入
-- prompt（_MEMORY_TOP_N 截断）；停用 = archived（不物理删除，保留归因链路）。
-- 种子 = 知识库温程《趋势理论》一次提炼（source='manual'、mem_type=discipline/method），
-- 方案 C：方法论反哺走 agent_memory 注入通道，不进选股 prompt 静态文案。
-- 幂等，可全量重放；与 init-scripts/01-schema.sql、03-seed.sql 保持同文案。

-- ---------------------------------------------------------------------------
-- 1. 记忆表
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS agent_memory (
    id               BIGSERIAL PRIMARY KEY,
    mem_type         VARCHAR(16)  NOT NULL,      -- discipline 纪律 / method 方法 / lesson 教训
    title            VARCHAR(128) NOT NULL,
    body             TEXT         NOT NULL,
    source           VARCHAR(16)  NOT NULL,      -- auto 复盘自动提取 / manual 人工沉淀
    status           VARCHAR(16)  NOT NULL DEFAULT 'active',   -- active / archived（停用不删）
    source_result_id BIGINT,                     -- ai_analysis_result.id（auto 时必填，溯源）
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agent_memory_source_title UNIQUE (source_result_id, title)
);

CREATE INDEX IF NOT EXISTS idx_agent_memory_status ON agent_memory(status, mem_type);

COMMENT ON TABLE agent_memory IS
    '交易 Agent 自有记忆（方法论纪律 + 复盘沉淀，反哺每日计划，docs/plan/paper-trading-plan.md §12.1）';

-- ---------------------------------------------------------------------------
-- 2. 种子：温程《趋势理论》核心纪律与方法（知识库 kb_source id=1 提炼）
--    幂等按 title 去重：种子行存在（含被停用/编辑）即跳过。
-- ---------------------------------------------------------------------------

INSERT INTO agent_memory (mem_type, title, body, source, status)
SELECT 'discipline', '选股本质是选板块：无板块效应不参与',
       '选股必须选板块（趋势理论第一原则）：只参与板块效应成立的方向——板块内至少三只以上涨停、多只涨幅 7% 以上个股助攻形成联动；独涨无联动的个股不参与。这属于交易纪律：违规偶尔尝到甜头，下一次也一定会出问题。（温程《趋势理论》）', 'manual', 'active'
WHERE NOT EXISTS (SELECT 1 FROM agent_memory WHERE title = '选股本质是选板块：无板块效应不参与');

INSERT INTO agent_memory (mem_type, title, body, source, status)
SELECT 'discipline', '不碰后排被动上涨个股',
       '板块中未率先封板、被其他涨停股带动的后排个股属于被动上涨，板块走弱时往往最先被砸至跌停；只做率先启动的前排强势股。（温程《趋势理论》）', 'manual', 'active'
WHERE NOT EXISTS (SELECT 1 FROM agent_memory WHERE title = '不碰后排被动上涨个股');

INSERT INTO agent_memory (mem_type, title, body, source, status)
SELECT 'discipline', '位置优先：M60 之下的个股不参与',
       '先看位置再谈技术：日线或周线处于 M60（60 日均线）之下且趋势线斜向下的下降通道个股，即使出现涨停也没有参与意义；只做 M60 之上、处于上升通道的标的。（温程《趋势理论》）', 'manual', 'active'
WHERE NOT EXISTS (SELECT 1 FROM agent_memory WHERE title = '位置优先：M60 之下的个股不参与');

INSERT INTO agent_memory (mem_type, title, body, source, status)
SELECT 'discipline', '横盘不埋伏，等放量涨停启动',
       '日线横盘（震荡区间）不提前埋伏，等待放量涨停突破平台、确认启动点再介入；突破必须是真的涨停——差一分钱未封死的涨停属无效突破，这种启动不能用。（温程《趋势理论》）', 'manual', 'active'
WHERE NOT EXISTS (SELECT 1 FROM agent_memory WHERE title = '横盘不埋伏，等放量涨停启动');

INSERT INTO agent_memory (mem_type, title, body, source, status)
SELECT 'method', '三元一催化是开仓总开关',
       '天时（大盘企稳或活跃：M5 之上或阻尼运动横住）+ 地利（板块效应加题材）+ 人和（个股联动出现龙头：至少三个以上涨停建制）三者同时具备且有题材催化才可开仓交易；不符合就休息。打板与技术形态是术，三元一催化是道。（温程《趋势理论》）', 'manual', 'active'
WHERE NOT EXISTS (SELECT 1 FROM agent_memory WHERE title = '三元一催化是开仓总开关');

INSERT INTO agent_memory (mem_type, title, body, source, status)
SELECT 'discipline', '机会只在拐点：无板块联动期坚决空仓',
       '交易不是天天可做，机会只在拐点上；大盘下降通道、市场无板块联动、情绪差时坚决空仓休息，不硬做。管住手：做错节奏会影响后续操作与心态，错过好过做错。（温程《趋势理论》）', 'manual', 'active'
WHERE NOT EXISTS (SELECT 1 FROM agent_memory WHERE title = '机会只在拐点：无板块联动期坚决空仓');

INSERT INTO agent_memory (mem_type, title, body, source, status)
SELECT 'method', '跟随市场：只做市场选出的最强龙头',
       '大盘、板块、龙头都是市场选的，交易者只做跟随；反弹周期中必须做龙头、做最强，只有最强的才最安全。不跟着别人买，依据必须来自自己的复盘。（温程《趋势理论》）', 'manual', 'active'
WHERE NOT EXISTS (SELECT 1 FROM agent_memory WHERE title = '跟随市场：只做市场选出的最强龙头');

INSERT INTO agent_memory (mem_type, title, body, source, status)
SELECT 'method', '见顶信号：高位巨量巨震大换手即线上卖点',
       '所有顶部出货的共同特征：高位巨量、换手 30% 以上、单日振幅 15%-20% 巨震（天地板/地天板典型），伴随双顶或反转 K 线组合即见顶——此为线上卖点，即使股价仍在五日线上也应卖出，不必等跌破安全带。大盘巨震标准为振幅 6%。（温程《趋势理论》）', 'manual', 'active'
WHERE NOT EXISTS (SELECT 1 FROM agent_memory WHERE title = '见顶信号：高位巨量巨震大换手即线上卖点');

INSERT INTO agent_memory (mem_type, title, body, source, status)
SELECT 'method', '启动是分歧转一致，见顶是一致转分歧',
       '启动阶段分歧转一致（筹码锁定、缩量上涨），高位放量是一致转分歧（筹码松动）即见顶。二板三板不换手则走不远（多止步五板）；换手补量平台以五日线为支撑、两到六日完成更强，十日线撑不住则放弃。（温程《趋势理论》）', 'manual', 'active'
WHERE NOT EXISTS (SELECT 1 FROM agent_memory WHERE title = '启动是分歧转一致，见顶是一致转分歧');

INSERT INTO agent_memory (mem_type, title, body, source, status)
SELECT 'discipline', '分时缩量诱多是常用分时卖点',
       '持仓股盘中拉高但量能萎缩（分时缩量诱多）即常用分时卖点；许多个股走势走坏都源于出现过此信号，掌握它对及时离场至关重要。（温程《趋势理论》）', 'manual', 'active'
WHERE NOT EXISTS (SELECT 1 FROM agent_memory WHERE title = '分时缩量诱多是常用分时卖点');

INSERT INTO agent_memory (mem_type, title, body, source, status)
SELECT 'discipline', '不求卖在最高点，抓最安全一段',
       '不要求卖在最高点也不要求买在最低点，抓住最安全的一段即可；卖掉就结束，换股做下一个机会，不后悔、不吃最后一口利润。（温程《趋势理论》）', 'manual', 'active'
WHERE NOT EXISTS (SELECT 1 FROM agent_memory WHERE title = '不求卖在最高点，抓最安全一段');

INSERT INTO agent_memory (mem_type, title, body, source, status)
SELECT 'discipline', '赢多胜小亏：仓位从轻靠时间积累',
       '财富积累靠一次次交易而非单笔重仓：符合三元一催化时大胆操作多赚钱，不符合时休息少亏钱；禁止单票满仓加杠杆搏一夜暴富。（温程《趋势理论》）', 'manual', 'active'
WHERE NOT EXISTS (SELECT 1 FROM agent_memory WHERE title = '赢多胜小亏：仓位从轻靠时间积累');

INSERT INTO agent_memory (mem_type, title, body, source, status)
SELECT 'method', 'M60 红包：前期龙头回落 M60 的套利模型',
       '前期强势龙头主升浪结束后回落至 M60 附近缩量企稳（不跌破）时出现的反弹即「红包」，越是前期龙头红包越大；跌破 M60 则行情结束不再参与；套利兑现要果断，盘面一走弱立刻卖出。（温程《趋势理论》）', 'manual', 'active'
WHERE NOT EXISTS (SELECT 1 FROM agent_memory WHERE title = 'M60 红包：前期龙头回落 M60 的套利模型');
