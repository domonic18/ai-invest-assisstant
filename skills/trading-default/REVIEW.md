---
name: 交易 Agent 共享复盘程序
description: 交易 Agent（trading-default）的日/周/月分层复盘共享作业程序：未建专属技能目录（skills/trading-<agent_key>/）的新 Agent 回退装载本技能。在当日盘面语境中做选股/计划/执行三层归因，逐条验证方法论纪律，提取可执行经验反哺次日计划。仅由交易 Agent 复盘定时任务（agent_paper_trade_review）消费，不属于助手可调用技能。
allowed-tools: []
---

# 交易 Agent 共享复盘程序

## 描述
全部交易 Agent 通用的复盘技能（D34 skill 化兜底）：不绑定特定交易风格，
人设视角由注册表注入。新 Agent 注册后未建专属技能目录时，复盘生成自动
装载本技能；后续可随时补建 `skills/trading-<agent_key>/REVIEW.md` 与
`review_prompt.yaml` 专属复盘程序（装载优先级：专属 → 共享）。

## 触发条件
- 定时任务 `agent_paper_trade_review`（交易日 19:00，先于 19:30 计划生成，复盘结论反哺次日计划）
- 周期由注册表 review_cadence 决定（daily 每交易日 / weekly 周期末 / monthly 月末）

## 作业流程
1. **输入就绪检查**：16:00 盘后同步落库（当日资金快照行存在）才开工；缺输入退避重试。
2. **盘面语境**：装载基准交易日的大盘复盘解读（大盘/主线板块/情绪位置），三层判定
   必须放进当日盘面语境校准——同样的交易行为发生在不同位置，评价不同。
3. **三层判定**：窗口内每笔委托独立给出 selection_verdict（该不该选）/ plan_verdict
   （买卖点、止损、仓位对不对）/ execution_verdict（是否按计划执行）。
4. **方法论验证**：对注册表绑定 KB 的全量纪律逐条表态——followed（遵守）/
   violated（违反，说明在哪几笔、代价是什么）/ not_applicable（本周期无涉及情境）。
5. **经验提取**：提炼具体到可执行的经验条目（纪律/方法/教训，含触发条件与动作），
   沉淀 agent_memory 反哺次日选股与计划。

## 纪律清单（硬约束）
- 好决策可能亏钱、坏决策可能赚钱：评估决策质量，不按单笔盈亏下结论。
- 盘面语境校准必做：解读缺失时如实说明，不假装看过语境。
- 方法论 disciplines 逐条验证，禁止跳过；违反必须量化代价；禁止编造不存在的纪律。
- 经验条目禁止空泛套话（如「要控制仓位」），只提取本周期真实体现的情境。

## 输出 Schema
```json
{
  "period": "day",
  "trade_date": "2026-09-26",
  "overall": "…",
  "market_context": "…",
  "trades": [
    {"cl_ord_id": "…", "stock_code": "600000", "selection_verdict": "correct",
     "plan_verdict": "correct", "execution_verdict": "correct", "reason": "…"}
  ],
  "bias": "…",
  "suggestion": "…",
  "methodology_check": [
    {"title": "…", "verdict": "not_applicable", "note": "…"}
  ],
  "experiences": [
    {"title": "…", "body": "…", "mem_type": "lesson"}
  ]
}
```
字段契约由服务层 `PaperTradeReviewContent` 钉死（全字段 required，禁默认值）；
trades 为空仍须给出 overall/bias/suggestion；缓存放 ai_analysis_result
（skill_id='paper-trade-review'，input_hash=Agent+账户+周期+窗口）。
