---
name: limit-up-review
description: 涨停 AI 归因：工具化获取涨停池全量明细、领涨板块与近两日新闻，按市场热点题材主线对涨停个股分组并给出涨停原因与个股题材标签。侧边栏助手手动生成与每日定时任务（limit-up-ai-review）均通过本 Skill 执行。
allowed-tools: get_limit_up_pool, get_sector_overview, search_news_by_date, persist_limit_up_attribution
---

# 涨停 AI 归因

## 描述
以工具实时取数为依据，对指定交易日的涨停板做题材归因：涨停池全量明细、领涨板块与主力资金、近两日新闻资讯。输出契约（groups/stock_themes）以 `LimitUpAttributionContent` 模型为准，最终回复必须且只能是符合「输出 Schema」的 JSON 对象。

## 触发条件
- 用户在侧边栏助手要求生成/重新生成涨停归因（如「生成今天的涨停归因」）
- 定时任务 limit-up-ai-review 每个交易日 16:30 自动生成

## 输出 Schema
```json
{
  "groups": [
    {"theme": "题材名", "reason": "涨停原因（1-2 句）", "stock_codes": ["000001", "600519"]}
  ],
  "stock_themes": {"000001": ["题材标签1", "题材标签2"]}
}
```
- `groups`：题材分组列表，按市场影响力排序（涨停家数多、连板高度高的排前）。
- `stock_themes`：每只涨停股的代码到 1-3 个题材标签的映射，必须逐一覆盖涨停池全部个股。
分区键缺一不可；股票代码必须是涨停池明细中出现的 6 位代码。

## 可用工具
- `get_limit_up_pool(trade_date)`: 涨停池全量明细——每只涨停股的代码、名称、所属行业、连板数、封板形态、首次封板时间。
- `get_sector_overview(trade_date)`: 行业板块概览——领涨板块（涨跌幅、涨停家数、主力净流入、代表个股）与资金净流入/净流出 TOP5。
- `search_news_by_date(start_date, end_date, limit)`: 按发布日期区间检索新闻/公告/研报标题与摘要（不限关键词，时间倒序）。

- `persist_limit_up_attribution(trade_date, groups, stock_themes)`: 将归因结果落库（仅助手对话路径注入），涨停页卡片自动刷新。

前三个为取数工具（独立执行器与助手路径均注入）；持久化工具仅助手对话路径注入，独立执行器路径由服务层 `limit_up_ai_service` 落库。

## 独立执行器路径流程
（定时任务路径）执行器注入前三个取数工具，最终回复输出符合「输出 Schema」的 JSON，服务层校验后落库。

## 助手对话路径流程
1-3 步取数同下；归因完成后**不要**在最终回复输出完整 JSON，而是调用
`persist_limit_up_attribution(trade_date, groups, stock_themes)` 落库，
并只用一两句话向用户总结分组结论；落库后涨停页自动刷新。

## 分析流程
1. 调用 `get_limit_up_pool(trade_date="{trade_date}")` 获取涨停池全量明细，通读每只个股的行业、连板数与封板形态。
2. 调用 `get_sector_overview(trade_date="{trade_date}")` 获取领涨板块（涨跌幅、涨停家数、主力净流入）与资金流向 TOP5。
3. 调用 `search_news_by_date(start_date="{trade_date 前一自然日}", end_date="{trade_date}", limit=30)` 获取近两日新闻资讯。
4. 按 system_prompt 的分组规则归因：以热点题材主线分组（允许跨行业合并）、单组不超过涨停总数的 40%、每组给出 1-2 句催化逻辑；优先依据新闻归纳，新闻不足时基于行业属性与资金动向合理归纳，禁止编造具体事件。
5. 逐一核对 `stock_themes` 覆盖涨停池全部个股后，输出符合「输出 Schema」的最终 JSON。

## 规则
- 只能使用涨停池明细中出现的股票代码，禁止编造或引入输入之外的个股。
- 题材名使用市场通用简称（如「算力/半导体产业链」「机器人」「并购重组」），禁止「其他」「综合」「杂项」等无信息量名称；确实无法归类的个股不放入任何分组。
- 每只个股 1-3 个题材标签（2-8 字简短名词），首标签与所属分组题材一致；一股只属一个分组，题材名不得重复。
- 全部使用简体中文；除最终 JSON 外不要输出长篇中间结论；工具调用失败时基于已有数据继续分析。
