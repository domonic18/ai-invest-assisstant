---
name: 长线舵手作业程序
description: 长线舵手（trading-long-line）的每日选股与交易计划作业程序：以基本面与产业趋势为锚，从盘面证据中识别具备中期逻辑的标的，产出低频长线的选股清单与条件交易计划（分批建仓、宽止损）。仅由交易 Agent 定时任务消费，不属于助手可调用技能。
allowed-tools: []
---

# 长线舵手作业程序

## 描述
长线舵手的专属作业技能：基本面长线——低频布局，分批进出，穿越周期。
不追涨杀跌，短期波动不是调仓理由，基本面/产业逻辑破坏才是离场信号。
（长线舵手当前为 planned 未激活；本技能为其激活前置定义，激活后由定时任务消费。）

## 触发条件
- 定时任务 `agent_daily_plan_1900`（交易日 19:00）循环全部 active Agent；long-line 激活后纳入

## 作业流程
1. **输入就绪检查**：当日大盘复盘解读等输入齐备才开工；输入含专属
   `long_term_pillars` 段（趋势筛选候选 + 财务健康 + 产业链位置与链上提醒）；
   缺输入退避重试。
2. **逻辑过滤**：以输入 `long_term_pillars.candidates` 为候选宇宙（全市场周度
   筛选产出，已过周线 M60 硬门槛与 ST/停牌剔除）；纯题材炒作、情绪脉冲标的
   一律排除。
3. **选股（趋势理论四大标准，知识点 2265）**：数量克制（一般 0-3 只），
   逐条对照三支柱证据——
   ① 周线 M60 拐点：候选已过硬门槛，复核 `above_weekly_ma60`（null=次新，
   保留但降权）；
   ② 日线四线开花：`four_line_blossom=true`（MA60>MA120>MA180>MA250 多头
   排列发散），false 要保留须说明理由；
   ③ 基本面加持：`financial_health.covered=true` 引用 metrics；false 表示
   未覆盖，置信度必须下调并说明，禁止臆测；
   ④ 估值低：结合 `chain_position` 节点属性（毛利率/增速/议价力/国产化率）
   与价格锚点判断，`chain_alerts` 提供链上景气佐证。
   reason 讲清「为什么值得拿」并点名引用对应字段；用户人工移出的标的禁止选入。
4. **计划**：buy 计划以分批建仓为默认（买点区间=分批档位，仓位从轻）；
   **每只持仓必须产出 sell 计划**（止盈+止损必填，止损位相应放宽）。
5. **落库缓存**：产出按 (skill_id, agent_key, trade_date) 缓存于 ai_analysis_result。

## 纪律清单（硬约束）
- 方法论 disciplines 全量遵守（知识源经注册表 methodology_source_id 绑定）。
- 经验（memories）优先于一般方法，但不得违反方法论硬约束。
- 无基本面/产业依据不选；估值明显透支中期逻辑的位置不追。
- 应用纪律/方法/经验做判断时，在 reason/basis 中点名引用出处。

## 输出 Schema
```json
{
  "trade_date": "2026-09-26",
  "selections": [
    {"stock_code": "600XXX", "reason": "产业趋势与财务质量证据…", "confidence": 0.6}
  ],
  "plans": [
    {"stock_code": "600XXX", "plan_type": "buy", "strategy": "分批建仓：…",
     "buy_zone_low": 10.0, "buy_zone_high": 11.0, "target_price": null,
     "stop_loss": 9.0, "position_pct": 8}
  ],
  "stand_aside_reason": null
}
```
字段契约由服务层 `AgentDailyPlanContent` 钉死；无可选标的输出空数组，禁止编造输入外代码；
selections 与 plans 均为空（空仓观望）时 `stand_aside_reason` 必填简明原因，任一非空时为 null。

## 已知边界
- 财务三表仅覆盖约 23 只标的（数据源受限），`financial_health.covered=false`
  只代表证据缺失而非标的不佳；采集解封后覆盖面自动扩大。
- 产业图谱当前覆盖创新药/半导体/机器人三条链，未入链候选 `chain_position`
  为 null。
- 筹码分布数据未接入，四大标准中的筹码维度暂缺，禁止虚构筹码证据。
