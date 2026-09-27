---
name: 短线猎手复盘程序
description: 短线猎手（trading-short-line）的日/周/月分层复盘作业程序：在当日盘面语境中做选股/计划/执行三层归因，逐条验证方法论纪律，提取可执行经验反哺次日计划。仅由交易 Agent 复盘定时任务（agent_paper_trade_review）消费，不属于助手可调用技能。
allowed-tools: []
---

# 短线猎手复盘程序

## 描述
短线猎手的专属复盘技能（D34 skill 化）：对专属模拟盘账户在指定周期内的委托与成交
做**分层归因复盘**。复盘的目的是让交易持续进步——强化做对的、修正做错的；
不以单笔盈亏论英雄，评估的是决策质量与纪律遵守。

## 触发条件
- 定时任务 `agent_paper_trade_review`（交易日 19:00，先于 19:30 计划生成，复盘结论反哺次日计划）
- 周期由注册表 review_cadence 决定（daily 每交易日 / weekly 周期末 / monthly 月末）

## 作业流程
1. **输入就绪检查**：16:00 盘后同步落库（当日资金快照行存在）才开工；缺输入退避重试。
2. **盘面语境**：装载基准交易日的大盘复盘解读（大盘/主线板块/情绪位置），三层判定
   必须放进当日盘面语境校准——买在启动段的回踩与买在退潮段的同样形态，性质完全不同。
3. **三层判定**：窗口内每笔委托独立给出 selection_verdict（该不该选）/ plan_verdict
   （买卖点、止损、仓位对不对）/ execution_verdict（是否按计划执行）。
4. **方法论验证**：对温程《趋势理论》KB 的全量纪律逐条表态——followed（遵守）/
   violated（违反，说明在哪几笔、代价是什么）/ not_applicable（本周期无涉及情境）。
5. **经验提取**：提炼具体到可执行的经验条目（纪律/方法/教训，含触发条件与动作），
   沉淀 agent_memory 反哺次日选股与计划。

## 纪律清单（硬约束）
- 好决策可能亏钱、坏决策可能赚钱：评估决策质量，不按单笔盈亏下结论。
- 短线语境优先：止损评价必须区分分歧日与退潮日；追高定性必须结合情绪位置。
- 方法论 disciplines 逐条验证，禁止跳过；违反必须量化代价。
- 经验条目禁止空泛套话（如「要控制仓位」），只提取本周期真实体现的情境。

## 输出 Schema
```json
{
  "period": "day",
  "trade_date": "2026-09-26",
  "overall": "…",
  "market_context": "…",
  "trades": [
    {"cl_ord_id": "…", "stock_code": "600815", "selection_verdict": "correct",
     "plan_verdict": "correct", "execution_verdict": "wrong", "reason": "…"}
  ],
  "bias": "…",
  "suggestion": "…",
  "methodology_check": [
    {"title": "不追高", "verdict": "followed", "note": "…"}
  ],
  "experiences": [
    {"title": "…", "body": "…", "mem_type": "lesson"}
  ]
}
```
字段契约由服务层 `PaperTradeReviewContent` 钉死（全字段 required，禁默认值）；
trades 为空仍须给出 overall/bias/suggestion；缓存放 ai_analysis_result
（skill_id='paper-trade-review'，input_hash=Agent+账户+周期+窗口）。
