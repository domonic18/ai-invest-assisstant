---
name: 长线舵手复盘程序
description: 长线舵手（trading-long-line）的日/周/月分层复盘作业程序：在当日盘面语境中做选股/计划/执行三层归因（基本面与产业趋势为锚），逐条验证方法论纪律，提取可执行经验反哺次日计划。仅由交易 Agent 复盘定时任务（agent_paper_trade_review）消费，不属于助手可调用技能。
allowed-tools: []
---

# 长线舵手复盘程序

## 描述
长线舵手的专属复盘技能（D34 skill 化）：对专属模拟盘账户在指定周期内的委托与成交
做**分层归因复盘**。复盘的目的是让交易持续进步——强化做对的、修正做错的；
不以单笔盈亏论英雄，评估的是决策质量与纪律遵守。

## 触发条件
- 定时任务 `agent_paper_trade_review`（交易日 19:00，先于 19:30 计划生成，复盘结论反哺次日计划）
- 周期由注册表 review_cadence 决定（daily 每交易日 / weekly 周期末 / monthly 月末）

## 作业流程
1. **输入就绪检查**：16:00 盘后同步落库（当日资金快照行存在）才开工；缺输入退避重试。
2. **盘面语境**：装载基准交易日的大盘复盘解读，三层判定放进当日盘面语境校准——
   长线视角下语境用于评估建仓时机（恐慌/分歧是分批窗口）与持仓容忍度（板块调整
   vs 系统性退潮）。
3. **三层判定**：窗口内每笔委托独立给出 selection_verdict（该不该选，基本面依据
   是否成立）/ plan_verdict（建仓节奏、宽止损是否合理）/ execution_verdict
   （是否按计划执行，短期波动恐慌减仓算 wrong）。
4. **方法论验证**：对注册表绑定 KB 的全量纪律逐条表态——followed（遵守）/
   violated（违反，说明在哪几笔、代价是什么）/ not_applicable（本周期无涉及情境）。
5. **经验提取**：提炼具体到可执行的经验条目（纪律/方法/教训，含触发条件与动作），
   沉淀 agent_memory 反哺次日选股与计划。

## 纪律清单（硬约束）
- 好决策可能亏钱、坏决策可能赚钱：评估决策质量，不按单笔盈亏下结论。
- 长线语境优先：短期波动不是调仓理由，逻辑破坏才是；评价离场决策看依据不看浮亏。
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
    {"cl_ord_id": "…", "stock_code": "600519", "selection_verdict": "correct",
     "plan_verdict": "correct", "execution_verdict": "wrong", "reason": "…"}
  ],
  "bias": "…",
  "suggestion": "…",
  "methodology_check": [
    {"title": "…", "verdict": "followed", "note": "…"}
  ],
  "experiences": [
    {"title": "…", "body": "…", "mem_type": "method"}
  ]
}
```
字段契约由服务层 `PaperTradeReviewContent` 钉死（全字段 required，禁默认值）；
trades 为空仍须给出 overall/bias/suggestion；缓存放 ai_analysis_result
（skill_id='paper-trade-review'，input_hash=Agent+账户+周期+窗口）。
