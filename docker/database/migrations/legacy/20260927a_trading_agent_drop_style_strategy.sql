-- D34：风格/策略描述字段全链路删除——trading_agent 两列退役
-- （此前只删了设置表单字段，注册表数据与介绍卡/能力卡/三处提示词注入仍在消费；
--   终态以 name/tagline + KB 方法论基座 + 技能包作业程序承载人设，无营销式文案字段）
ALTER TABLE trading_agent DROP COLUMN IF EXISTS strategy_desc;
ALTER TABLE trading_agent DROP COLUMN IF EXISTS style_desc;
