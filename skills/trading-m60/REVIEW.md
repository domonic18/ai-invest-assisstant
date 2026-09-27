---
name: 60分钟波段复盘程序
description: 60分钟波段（trading-m60）的日/周/月分层复盘作业程序：在当日盘面语境中做选股/计划/执行三层归因（M60 趋势与结构为锚），逐条验证方法论纪律，提取可执行经验反哺次日计划。仅由交易 Agent 复盘定时任务（agent_paper_trade_review）消费，不属于助手可调用技能。
allowed-tools: []
---

# 60分钟波段复盘程序

## 描述
60分钟波段的专属复盘技能（D34 skill 化）：对专属模拟盘账户在指定周期内的委托与
成交做**分层归因复盘**。复盘的目的是让交易持续进步——强化做对的、修正做错的；
不以单笔盈亏论英雄，评估的是决策质量与纪律遵守。

## 触发条件
- 定时任务 `agent_paper_trade_review`（交易日 19:00，先于 19:30 计划生成，复盘结论反哺次日计划）
- 周期由注册表 review_cadence 决定（daily 每交易日 / weekly 周期末 / monthly 月末）

## 作业流程
1. **输入就绪检查**：16:00 盘后同步落库（当日资金快照行存在）才开工；缺输入退避重试。
2. **盘面语境**：装载基准交易日的大盘复盘解读，三层判定放进当日盘面语境校准——
   波段视角下语境决定当下适合进攻、防守还是观望。
3. **三层判定**：窗口内每笔委托独立给出 selection_verdict（该不该选，M60 趋势与
   结构依据是否成立）/ plan_verdict（买点区间与结构破位止损是否对齐）/
   execution_verdict（是否按计划执行，结构未破坏恐慌出局算 wrong）。
4. **方法论验证**：对注册表绑定 KB 的全量纪律逐条表态——followed（遵守）/
   violated（违反，说明在哪几笔、代价是什么）/ not_applicable（本周期无涉及情境）。
5. **经验提取**：提炼具体到可执行的经验条目（纪律/方法/教训，含触发条件与动作），
   沉淀 agent_memory 反哺次日选股与计划。

## 纪律清单（硬约束）
- 好决策可能亏钱、坏决策可能赚钱：评估决策质量，不按单笔盈亏下结论。
- 波段语境优先：只用趋势语言评价决策——均线多空排列、关键位得失、量能配合；
  情绪化判断不作为评价依据。
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
    {"cl_ord_id": "…", "stock_code": "000001", "selection_verdict": "correct",
     "plan_verdict": "wrong", "execution_verdict": "correct", "reason": "…"}
  ],
  "bias": "…",
  "suggestion": "…",
  "methodology_check": [
    {"title": "…", "verdict": "violated", "note": "…"}
  ],
  "experiences": [
    {"title": "…", "body": "…", "mem_type": "discipline"}
  ]
}
```
字段契约由服务层 `PaperTradeReviewContent` 钉死（全字段 required，禁默认值）；
trades 为空仍须给出 overall/bias/suggestion；缓存放 ai_analysis_result
（skill_id='paper-trade-review'，input_hash=Agent+账户+周期+窗口）。
