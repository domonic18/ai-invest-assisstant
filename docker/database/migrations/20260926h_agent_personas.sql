-- 20260926h: 每个 Agent 的专属人设 prompt_id（agent-hub-plan.md D27）
-- 三个会话人设 YAML：trading_agent_short_line / trading_agent_long_line / trading_agent_m60
-- 计划作业程序走 skills/trading-<agent_key>/ 技能目录（无需 DDL）

UPDATE trading_agent SET prompt_id = 'trading_agent_short_line'
WHERE agent_key = 'short-line' AND prompt_id <> 'trading_agent_short_line';

UPDATE trading_agent SET prompt_id = 'trading_agent_long_line'
WHERE agent_key = 'long-line' AND prompt_id <> 'trading_agent_long_line';

UPDATE trading_agent SET prompt_id = 'trading_agent_m60'
WHERE agent_key = 'm60' AND prompt_id <> 'trading_agent_m60';

-- 行一律显式给 prompt_id；旧默认 'trading_agent' 指向已删除的共享文件，无意义
ALTER TABLE trading_agent ALTER COLUMN prompt_id DROP DEFAULT;
