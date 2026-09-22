-- 20260922a: 移除技能优化建议单表（功能整体下线，未来方向改为模拟盘盈亏复盘驱动，另行立项）
-- 幂等：重复执行无副作用。已应用 20260921c 的环境（如本地 dev）由此回收该表。
DROP TABLE IF EXISTS kb_optimization_suggestion;
