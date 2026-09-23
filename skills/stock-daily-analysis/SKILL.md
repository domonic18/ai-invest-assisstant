---
name: stock-daily-analysis
description: 个股每日收盘分析：工具化获取个股行情快照、日 K 线、预计算技术面（通道/拐点）、情绪面（板块资金/连板/个股资金）、财务指标与近期新闻，产出按分区组织的结构化每日分析，维度对齐大盘复盘。个股详情页触发生成与自选股 AI 复盘定时任务均通过本 Skill 执行。
allowed-tools: get_stock_quote, get_stock_kline, get_stock_technical, get_stock_emotion_context, query_financial_data, search_news, search_knowledge_base, get_trade_calendar, persist_stock_daily_analysis
---

# 个股每日分析

## 描述
以工具实时取数为依据，为单只股票生成当日收盘分析：盘面摘要、技术面分析、情绪面分析、关键事件、操作策略、风险与止损六个分区，与大盘复盘同为「技术面×情绪面×消息面互证」框架，只是对象收敛到个股。分析流程与工具编排由本文件维护，输出分区契约（key 集合）以 `skills/stock-daily-analysis/prompt.yaml` 为准。

## 触发条件
- 个股详情页请求生成当日 AI 分析
- 自选股分组开启 AI 复盘后的每日定时任务（stock_daily_analysis_1640）

## 输出 Schema
产出统一为六个分区（key 集合以 `skills/stock-daily-analysis/prompt.yaml` 为准）：

```json
{
  "sections": {
    "intraday_review": "盘面摘要（一句话结论，Markdown）",
    "technical_analysis": "技术面分析（Markdown）",
    "emotion_analysis": "情绪面分析（Markdown）",
    "key_events": "关键事件（Markdown）",
    "strategy": "操作策略（Markdown）",
    "risk_lines": "风险与止损（Markdown）"
  }
}
```

分区 key 必须与任务指令中声明的完全一致，缺一不可，值必须是非空 Markdown 字符串。

按运行路径二选一交付：
- **助手对话路径**（任务指令要求调用 `persist_stock_daily_analysis`）：撰写完六分区后，将其作为 `sections` 参数传入该工具保存，不要在回复中输出 JSON。
- **独立执行器路径**（定时任务等直接执行）：最终回复必须且只能是上述 JSON 对象，不要 markdown 代码围栏、不要额外解释文字。

## 可用工具
执行器路径固定注入前六个取数工具与 `search_knowledge_base`；`get_trade_calendar` 仅助手对话路径可用。
- `get_stock_quote(stock_code)`: 最新行情快照——现价、开高低收、涨跌幅、成交量/额、市值（Redis 实时缺失时回退最近日 K）。
- `get_stock_kline(stock_code, limit=30)`: 近期日 K（日期、开高低收、量、额、涨跌幅），按交易日倒序；本分析传 `limit=20`，用于盘面摘要的区间位置判断。
- `get_stock_technical(stock_code, trade_date?)`: 预计算技术分析文本——通道归属（上升/下降/阻尼运动）、均线关系、支撑/突破/风险三类拐点信号（「趋势概要」行）、新低/地量/放量、60 日前低支撑、周线形态；拐点与通道结论直接引用该文本，禁止自行估算。
- `get_stock_emotion_context(stock_code, trade_date?)`: 情绪面上下文——所在行业主力资金净流入与全行业排名、近 5 日累计；个股近 5 日主力资金流；个股当日涨停/连板状态（封板结构）；行业涨停家数；市场涨停结构（总数/首板/连板/最高板）。资金净流入为正、净流出为负。
- `query_financial_data(stock_codes, periods=3)`: 核心财务指标——最新报告期毛利率、营收同比、研发占比、应收账款周转；仅作操作策略分区的一句基本面背景，不展开。
- `search_news(keyword, days=30, limit=15)`: 按关键词检索近期新闻/公告/研报标题与摘要，仅用于关键事件分区收录明确相关的消息事件。
- `search_knowledge_base(query, source?, chapter?, point_type?, include_media?)`: 助手对话与独立执行器路径均注入——检索投资课程知识库已审核知识卡片，为走势形态与操作策略补充课程方法论佐证（如形态识别纪律、量价关系方法）。引用卡片时必须保留返回的 citation 定位（集数/时间码/章节/页码）使结论可溯源；`include_media` 仅在用户想学习知识点的课程讲解、或明确要求看视频原片/书籍原文时传 true，分析中保持 false；未注入本工具时（如对话关闭知识库开关）不得编造知识库引用。
- `get_trade_calendar()`: 仅助手对话路径可用——当前北京时间、今天是否交易日、最近（含今日）交易日。

## 分析流程

### 步骤 0：交易日确认
助手对话路径先调用 `get_trade_calendar` 获取最近交易日；独立执行器路径直接使用任务指令给定的 trade_date。取数后若发现 K 线最新日期早于最近交易日，说明当日数据尚未采集完成：在盘面摘要分区开头披露「最近交易日应为 X，数据截至 Y」，随后以实际数据日期 Y 完成分析，不得把 Y 表述为最近交易日。

### 步骤 1：行情快照
调用 `get_stock_quote(stock_code=...)` 获取当日盘面数据。若返回为空，后续以 K 线最近一根 bar 为盘面依据。

### 步骤 2：日 K 区间定位
调用 `get_stock_kline(stock_code=..., limit=20)` 获取近 20 个交易日走势，用于盘面摘要的区间位置判断（新高/新低/区间中上沿/中下沿）。识别出典型形态（如突破、缺口、顶部/底部结构）或对走势定性存在不确定时，调用 `search_knowledge_base(query=<形态/量价相关关键词>)` 检索课程方法论佐证。

### 步骤 3：技术面（get_stock_technical）
调用 `get_stock_technical(stock_code=..., trade_date=...)` 获取预计算技术分析文本。技术面分析分区以此为唯一依据：
- 通道归属（上升通道/下降通道/阻尼运动/均线交错）用定性描述；
- 文本「趋势概要」行出现支撑拐点/突破拐点/风险拐点时明确指出并说明量能配合情况，拐点结论直接引用原文，禁止自行估算；
- 禁止罗列具体点位数值与均线数值清单。

### 步骤 4：情绪面（get_stock_emotion_context）
调用 `get_stock_emotion_context(stock_code=..., trade_date=...)` 获取情绪面上下文，三路互证：
- 所在行业主力资金（净流入/流出带正负号、全行业排名、近 5 日累计）；
- 个股近 5 日主力资金趋势，与行业资金方向印证或背离；
- 个股涨停/连板状态 + 行业涨停家数 + 市场涨停结构（总数/首板/连板/最高板），据此定位该股所处情绪位置（主流主线/跟风/冰点）。
数据缺失的字段如实说明，不得臆测。

### 步骤 5：财务背景（可选）
调用 `query_financial_data(stock_codes=[stock_code], periods=3)` 获取基本面指标，仅在操作策略分区作一句基本面背景参考，不展开成段。

### 步骤 6：消息面检索（关键事件分区专用，收紧）
调用 `search_news(keyword=<股票名称>, days=14, limit=8)` 检索近期消息。仅当检索结果明确与该股相关时才写入关键事件分区（日期 + 事件一句话 + 影响方向）；关键事件分区禁止任何行情复述（开高低收、涨跌幅、量能、K 线形态、缺口等均不得出现——量价信息归盘面摘要与技术面分区）；无明确相关事件时整分区只输出一句「数据范围内未观察到明显事件」。

### 步骤 7：方法论对照（供 technical_analysis / strategy / risk_lines 分区）
系统提示已附《趋势理论》方法论手册（趋势与通道判断、量价关系、关键位与支撑压力、仓位与止损纪律的分章蒸馏条目，每条带课程 citation）：撰写技术面、操作策略与风险止损分区时对照手册条目支撑判断，引用时原样保留「《趋势理论》第N集 MM:SS（章节）」定位；确无适用方法论时在该分区末尾另起一行输出 `> 知识库佐证：无适用方法论`；手册未覆盖的长尾主题可调用 `search_knowledge_base` 补充检索（引用格式一致）；禁止编造引用。

### 步骤 8：撰写分区并交付
基于以上数据撰写六个分区，按任务指令选择交付方式：助手对话路径调用 `persist_stock_daily_analysis(stock_code, trade_date, sections)` 保存；独立执行器路径按「输出 Schema」输出 JSON。

## 用户画线解读
任务指令附带的「用户画线参考」是用户在 K 线图上手动绘制的技术标注（线段/射线/水平线/箱体/文字）：
- 几何形态（价位、日期区间）代表用户标记的关键位置，支撑/压力/止损分析须与之对照。
- 标注文字是一等信号，代表用户对形态的命名与判断：采纳时直接引用；存在分歧时在相关分区显式指出分歧及依据，不得无视或静默改写。

## 规则
- 所有文本使用简体中文，Markdown 语法，每个分区 2-4 个要点、每点一行，禁止整段连排。
- 行情报价（开高低收）只在盘面摘要分区以定性结论出现一次，其余分区禁止复述点位；技术面分析禁止罗列具体点位数值与均线数值清单。
- 重点结论用 **加粗** 强调；关键价位、成交量额用 `行内代码` 高亮。
- 涨跌幅百分比必须带正负号（如 +3.05%、-1.20%）；资金流向金额必须带正负号（净流入为正、净流出为负，如 +1.2 亿）。
- 金额换算为亿元或万元，与工具返回口径一致。
- 不得编造数据中不存在的价位、事件或消息；支撑/压力与止损位必须来自实际数据的高低点。
- 数据不足（K 线缺失或不足 20 日）或滞后于最近交易日时，在盘面摘要分区说明实际数据范围。
- 各分区是同一盘面的不同切面：撰写时与其他分区信号相互印证或指出背离，禁止只基于单一维度在操作策略下结论。
- 客观提示风险，不给出确定性的涨跌预测，不构成投资建议。
- 除最终 JSON 外，不要输出长篇中间结论；工具调用失败时基于已有数据继续分析并在相关分区说明。

## 示例
用户指令："请生成 贵州茅台（600519）2026-09-01 的每日个股分析……"

1. `get_stock_quote(stock_code="600519")` → 现价、涨跌幅、量额。
2. `get_stock_kline(stock_code="600519", limit=20)` → 近 20 日区间位置。
3. `get_stock_technical(stock_code="600519")` → 通道归属/趋势概要拐点。
4. `get_stock_emotion_context(stock_code="600519")` → 行业资金与排名、个股资金、涨停结构。
5. `query_financial_data(stock_codes=["600519"], periods=3)` → 毛利率/营收同比（一句背景）。
6. `search_news(keyword="贵州茅台", days=14, limit=8)` → 消息面（无相关事件则关键事件分区一句带过）。
7. `search_knowledge_base(query="放量突破 形态 买入纪律")` → 课程方法论佐证（走势存在典型形态时）。
8. 最终回复：`{"sections": {"intraday_review": "- **缩量整理**……", "technical_analysis": "……", "emotion_analysis": "……", "key_events": "……", "strategy": "……", "risk_lines": "……"}}`
