---
name: stock-daily-analysis
description: 个股每日收盘分析：工具化获取个股行情快照、日 K 线、财务指标与近期新闻，产出按分区组织的结构化每日分析。个股详情页触发生成与自选股 AI 复盘定时任务均通过本 Skill 执行。
allowed-tools: get_stock_quote, get_stock_kline, query_financial_data, search_news
---

# 个股每日分析

## 描述
以工具实时取数为依据，为单只股票生成当日收盘分析：盘面解读、关键事件、操作策略、风险与止损四个分区。分析流程与工具编排由本文件维护，输出分区契约（key 集合）以 `backend/app/prompts/skills/stock-daily-analysis.yaml` 为准。

## 触发条件
- 个股详情页请求生成当日 AI 分析
- 自选股分组开启 AI 复盘后的每日定时任务（stock_daily_analysis_1640）

## 输出 Schema
产出统一为四个分区（key 集合以 `backend/app/prompts/skills/stock-daily-analysis.yaml` 为准）：

```json
{
  "sections": {
    "intraday_review": "盘面解读（Markdown）",
    "key_events": "关键事件（Markdown）",
    "strategy": "操作策略（Markdown）",
    "risk_lines": "风险与止损（Markdown）"
  }
}
```

分区 key 必须与任务指令中声明的完全一致，缺一不可，值必须是非空 Markdown 字符串。

按运行路径二选一交付：
- **助手对话路径**（任务指令要求调用 `persist_stock_daily_analysis`）：撰写完四分区后，将其作为 `sections` 参数传入该工具保存，不要在回复中输出 JSON。
- **独立执行器路径**（定时任务等直接执行）：最终回复必须且只能是上述 JSON 对象，不要 markdown 代码围栏、不要额外解释文字。

## 可用工具
- `get_stock_quote(stock_code)`: 最新行情快照——现价、开高低收、涨跌幅、成交量/额、市值（Redis 实时缺失时回退最近日 K）。
- `get_stock_kline(stock_code, limit=30)`: 近期日 K（日期、开高低收、量、额、涨跌幅），按交易日倒序；本分析传 `limit=20`。
- `query_financial_data(stock_codes, periods=3)`: 核心财务指标——最新报告期毛利率、营收同比、研发占比、应收账款周转。
- `search_news(keyword, days=30, limit=15)`: 按关键词检索近期新闻/公告/研报标题与摘要，用于关键事件分区的消息面佐证。

## 分析流程

### 步骤 1：行情快照
调用 `get_stock_quote(stock_code=...)` 获取当日盘面数据。若返回为空，后续以 K 线最近一根 bar 为盘面依据。

### 步骤 2：日 K 走势
调用 `get_stock_kline(stock_code=..., limit=20)` 获取近 20 个交易日走势，判断区间位置（新高/新低/震荡）、量价配合与形态。

### 步骤 3：财务背景
调用 `query_financial_data(stock_codes=[stock_code], periods=3)` 获取基本面指标，为策略分区提供基本面佐证。

### 步骤 4：消息面检索（可选）
调用 `search_news(keyword=<股票名称>, days=14, limit=8)` 检索近期消息。仅当检索结果明确与该股相关时才可写入关键事件分区，否则注明"数据范围内未观察到明显事件"。

### 步骤 5：撰写分区并交付
基于以上数据撰写四个分区，按任务指令选择交付方式：助手对话路径调用 `persist_stock_daily_analysis(stock_code, trade_date, sections)` 保存；独立执行器路径按「输出 Schema」输出 JSON。

## 规则
- 所有文本使用简体中文，Markdown 语法，每个分区 2-4 个要点、每点一行，禁止整段连排。
- 重点结论用 **加粗** 强调；关键价位、成交量额用 `行内代码` 高亮。
- 涨跌幅百分比必须带正负号（如 +3.05%、-1.20%）。
- 金额换算为亿元或万元，与工具返回口径一致。
- 不得编造数据中不存在的价位、事件或消息；支撑/压力与止损位必须来自实际数据的高低点。
- 数据不足（K 线缺失或不足 20 日）时在相关分区开头说明实际数据范围。
- 客观提示风险，不给出确定性的涨跌预测，不构成投资建议。
- 除最终 JSON 外，不要输出长篇中间结论；工具调用失败时基于已有数据继续分析并在相关分区说明。

## 示例
用户指令："请生成 贵州茅台（600519）2026-09-01 的每日个股分析……"

1. `get_stock_quote(stock_code="600519")` → 现价、涨跌幅、量额。
2. `get_stock_kline(stock_code="600519", limit=20)` → 近 20 日走势。
3. `query_financial_data(stock_codes=["600519"], periods=3)` → 毛利率/营收同比。
4. `search_news(keyword="贵州茅台", days=14, limit=8)` → 消息面（可跳过）。
5. 最终回复：`{"sections": {"intraday_review": "- **高开回落**……", "key_events": "……", "strategy": "……", "risk_lines": "……"}}`
