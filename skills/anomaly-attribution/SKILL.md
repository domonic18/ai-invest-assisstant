---
name: anomaly-attribution
description: 异动 AI 归因：对规则检测出的板块/个股异动（强度榜 top-N），经新闻、龙虎榜、资金流证据工具取数后给出归因分类与摘要。检测任务尾部定时批量归因与异动页「AI 归因」按钮的手动重分析均通过本 Skill 执行。
allowed-tools: search_news_by_date, search_news, get_dragon_tiger, get_stock_fund_flow, get_sector_fund_flow, persist_sector_anomaly_attribution, persist_stock_anomaly_attribution
---

# 异动 AI 归因

## 描述
规则算子已回答「发生了什么异动」（趋势 MA60 + 量价维度，见异动检测服务）；本 Skill 只回答「为什么」：调用证据工具核实消息面 / 资金面 / 龙虎榜，对每一条异动给出归因分类（可修正规则分类）与 1-2 句归因摘要。证据只进入摘要文本，不得编造检测数据之外的事实。最终回复必须且只能是符合「输出 Schema」的 JSON 对象。

## 触发条件
- 检测任务（sector-anomaly / stock-anomaly）尾部对强度榜 top-N 批量归因（板块 10 / 个股 20）
- 用户在异动页点击「AI 归因」按钮，经侧边栏助手手动生成/重新生成

## 输出 Schema
板块域（sector）：
```json
{"items": [{"sector_type": "industry|concept", "sector_code": "板块代码", "category": "resonance|rotation", "summary": "归因摘要（1-2 句）"}]}
```
个股域（stock）：
```json
{"items": [{"stock_code": "6 位代码", "category": "breakout|acceleration|pullback", "summary": "归因摘要（1-2 句）"}]}
```
- `category` 语义：板块 resonance=趋势共振（多主线同向）、rotation=轮动补涨；个股 breakout=趋势突破启动、acceleration=趋势内加速、pullback=下跌反抽。
- `items` 必须覆盖输入清单中的全部标的，禁止新增清单外的标的；summary 必须简体中文。

## 可用工具
- `search_news_by_date(start_date, end_date, limit)`: 按日期区间检索新闻/公告/研报标题与摘要。
- `search_news(query, limit)`: 按关键词检索资讯知识库。
- `get_dragon_tiger(stock_code, trade_date)`: 龙虎榜上榜记录（上榜原因、净买额）——个股证据。
- `get_stock_fund_flow(stock_code, days)`: 个股主力资金分档净流入——个股证据。
- `get_sector_fund_flow(sector_type, days, top)`: 板块主力资金净流入排行——板块证据。
- `persist_sector_anomaly_attribution(trade_date, items)` / `persist_stock_anomaly_attribution(trade_date, items)`: 归因落库（仅助手对话路径注入），异动页自动刷新。

## 分析流程
1. 通读输入清单中每条异动的规则事实（命中维度、强度、趋势状态、分类）。
2. 板块域：对强度靠前的板块调 `get_sector_fund_flow` 核实主力资金；个股域：对上榜/高换手个股调 `get_dragon_tiger` 与 `get_stock_fund_flow` 核实资金与龙虎榜证据。
3. 调 `search_news_by_date(start_date="{trade_date} 前一自然日", end_date="{trade_date}", limit=30)` 获取近两日新闻；对关键个股/板块可再用 `search_news` 收敛。
4. 逐条归因：优先引用新闻事件，其次资金面（主力净流入/龙虎榜净买额），再次行业逻辑；证据不足时基于板块/行业属性给出保守归纳并明确「或系」，**禁止编造具体事件、政策名称或数据**。
5. 校正 `category`：规则分类与证据明显矛盾时以证据为准；无把握时保留规则分类。
6. 输出符合「输出 Schema」的最终 JSON（summary 覆盖全部输入标的）。

## 规则
- 证据仅用于摘要文本，不改变异动的检测维度与强度。
- 摘要 1-2 句、简体中文，可直接引用来源类型（如「据龙虎榜」「板块主力净流入居前」），不写 HTML/markdown。
- 上榜代码必须来自输入清单；清单外标的一律不输出。
- 全部使用中文；工具调用失败时基于已有规则事实继续归因。
