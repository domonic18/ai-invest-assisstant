---
name: 交易 Agent 共享作业程序
description: 交易 Agent（trading-default）的每日选股与交易计划共享作业程序：未建专属技能目录（skills/trading-<agent_key>/）的新 Agent 回退装载本技能。基于方法论基座（注册表 methodology_source_id 绑定的 KB）、当日复盘解读、涨停归因与异动记录，产出选股清单与次日条件交易计划。仅由交易 Agent 定时任务（agent_daily_plan_1900）消费，不属于助手可调用技能。
allowed-tools: []
---

# 交易 Agent 共享作业程序

## 描述
全部交易 Agent 通用的作业技能（D28 扩展性兜底）：不绑定特定交易风格，
人设视角由注册表注入。新 Agent 注册后未建专属技能目录时，计划生成自动
装载本技能；后续可随时补建 `skills/trading-<agent_key>/` 专属作业程序
（风格化侧重优于共享默认）。

## 触发条件
- 定时任务 `agent_daily_plan_1900`（交易日 19:00）：对全部 active 交易 Agent 循环生成，本技能服务于无专属目录的 agent_key

## 作业流程
1. **输入就绪检查**：当日大盘复盘解读、涨停归因、异动记录齐备才开工；缺输入退避重试。
2. **盘面定位**：用复盘解读 + 涨停归因识别当日市场主线与情绪位置。
3. **选股**：只从有输入依据的标的中选（复盘结论/涨停题材/异动归因），
   符合方法论参与条件的优先；宁缺毋滥，一般 0-5 只；用户人工移出的标的禁止选入。
4. **计划**：buy 计划给买点区间与止损；**每只持仓必须产出 sell 计划**（止盈+止损必填）。
5. **落库缓存**：产出按 (skill_id, agent_key, trade_date) 缓存于 ai_analysis_result，重跑命中缓存。

## 纪律清单（硬约束）
- 方法论 disciplines 全量遵守：参与条件、位置要求、卖点纪律不满足的候选宁可放弃。
- 经验（memories）优先于一般方法（更贴近本账户实际），但不得违反方法论硬约束。
- 应用纪律/方法/经验做判断时，在 reason/basis 中点名引用出处。
- 没有明确依据就不选，没有明确买卖点就不出计划。

## 输出 Schema
```json
{
  "trade_date": "2026-09-26",
  "selections": [
    {"stock_code": "600815", "reason": "遵循〈选股本质是选板块〉：主线板块回踩企稳…", "confidence": 0.7}
  ],
  "plans": [
    {"stock_code": "600815", "plan_type": "buy", "strategy": "…", "buy_zone_low": 10.2,
     "buy_zone_high": 10.8, "target_price": null, "stop_loss": 9.8, "position_pct": 10}
  ]
}
```
字段契约由服务层 `AgentDailyPlanContent` 钉死；无可选标的输出空数组，禁止编造输入外代码。

## 方法论基座
注册表 methodology_source_id 绑定的知识库（缺省温程《趋势理论》）：
纪律层全量注入 + 总纲 + 按当日盘面检索的相关方法；交易经验沉淀于 agent_memory。
