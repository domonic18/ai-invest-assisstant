---
name: industry-chain-analysis
description: 产业链分析：拆解指定行业的上下游结构，识别各环节代表上市公司并对比财务表现与竞争格局，产出结构化产业链分析与投资观点。当用户要求产业链体检/上下游/供应链/价值链分析时使用。
allowed-tools: query_industry_companies, query_financial_data, search_news, search_vector_kb, persist_chain_analysis
---

# Industry Chain Analysis Skill

## Description
Analyze the upstream and downstream supply chain of a specified industry. Identify representative listed companies at each node of the chain, compare their financial performance, and output a structured industry chain graph with investment insights.

## Triggers
- User asks to analyze an industry's supply chain / value chain
- User asks about upstream/downstream relationships of an industry
- User wants to understand competitive landscape within an industry chain
- Keywords: 产业链, 上下游, 供应链, 价值链, 行业分析, industry chain

## Output Schema
You must produce a JSON object matching `ChainAnalysisResult` schema with these top-level fields:

```json
{
  "nodes": [...],
  "edges": [...],
  "summary": "string",
  "value_distribution": {...},
  "opportunities": [...],
  "risks": [...],
  "key_companies_summary": [...]
}
```

### Node schema
- `name`: str, 环节名称（具体细分产品/材料/设备/应用领域）
- `type`: str, 取值 upstream / midstream / downstream
- `description`: str, 不超过 60 字
- `companies`: list of { `code`: 6 位股票代码, `name`: 公司名称 }
- `avg_gross_margin`: float | null, 毛利率百分比数值，如 25.3
- `revenue_growth`: float | null, 营收同比百分比数值
- `rd_ratio`: float | null, 研发占比百分比数值
- `bargaining_power`: float | null, 0-100 评分
- `localization_rate`: float | null, 0-100 国产化率估计
- `tech_barrier`: "high" | "medium" | "low" | null
- `bottleneck_indicators`: list[str], 瓶颈/卡脖子因素
- `recent_breakthroughs`: list[str], 近期突破/扩产信号

### Edge schema
- `source`: str, 起点环节名称（必须匹配某个 node.name）
- `target`: str, 终点环节名称（必须匹配某个 node.name）
- `relation`: str, 供应/委托/需求关系描述
- `strength`: int, 0-100 关联强度
- `description`: str, 关系补充说明
- `criticality`: "high" | "medium" | "low" | null

### value_distribution schema
- `highest_margin_segment`: str | null
- `highest_margin_value`: float | null
- `lowest_margin_segment`: str | null
- `lowest_margin_value`: float | null

### opportunities / risks schema
- `title`: str
- `description`: str
- `related_segment`: str | null
- `confidence` / `severity`: "high" | "medium" | "low" | null

### key_companies_summary schema
- `code`: str, 6 位股票代码
- `name`: str
- `chain_position`: str | null
- `score`: float | null, 0-100

## Available Tools
- `query_industry_companies(industry, limit=150)`: 按行业名称查询上市公司清单，返回股票代码、名称、二级/三级行业、经营范围。
- `query_financial_data(stock_codes, periods=3)`: 批量查询公司核心财务指标：毛利率、营收同比、研发占比、应收周转。
- `search_news(keyword, days=30, limit=15, doc_types=None)`: 检索近期新闻/公告/研报标题与摘要。
- `search_vector_kb(query, limit=5)`: 检索研报/年报知识库片段。
- `persist_chain_analysis(industry, result)`: 将最终符合 schema 的 JSON 结果持久化到数据库，生成新版本并在产业链页面展示。

## Analysis Workflow

### Step 1: Collect company list
Call `query_industry_companies(industry=...)` to fetch all listed companies in the target industry.

### Step 2: Collect financial metrics
Select up to 40 representative companies from the list (prioritize companies with clear business scope related to the industry). Call `query_financial_data(stock_codes=[...], periods=3)` to get gross margin, revenue growth, R&D ratio, and receivables turnover.

### Step 3: Collect qualitative evidence
Call `search_news(keyword=..., days=30, limit=15)` and `search_vector_kb(query=..., limit=5)` to gather recent industry dynamics, capacity expansion signals, and analyst views. Recommended queries:
- `{industry} 产业链 供应商 客户 上下游`
- `{industry} 主营业务 经营范围`

### Step 4: Derive segments bottom-up
Based on company business scopes and financial evidence, cluster companies into concrete segments. Rules:
- Segment names must be specific products, materials, equipment, or application areas.
- Forbidden examples (too broad): "半导体材料", "设备制造", "下游应用"
- Good examples: "光刻胶", "CMP 抛光材料", "刻蚀设备", "功率器件"
- Total segments usually 15-25, never fewer than 10 unless the industry itself is very narrow.

### Step 5: Organize upstream / midstream / downstream
Assign each segment a `type`:
- `upstream`: raw materials, components, equipment
- `midstream`: manufacturing, integration, foundry
- `downstream`: applications, terminals, channels

Build `edges` between segments based on supply / commission / demand relationships. Each edge must reference existing node names.

### Step 6: Compute segment-level metrics
For each segment, compute averages from the financial metrics of its companies. If a segment has no financial data, use `null`. Never fabricate numbers.

### Step 7: Identify key companies
Select at least 3 most noteworthy companies across the whole chain. Score them 0-100 based on financial health, chain position, and growth potential.

### Step 8: Identify opportunities and risks
Based on financial evidence and qualitative research, generate 3-6 opportunities and 3-6 risks. Include `confidence`/`severity` and `related_segment` when applicable.

### Step 9: Persist result
Construct the final JSON object and call `persist_chain_analysis(industry=..., result=...)`. The tool will save it and return `version_id`, `version_no`, `status`.

## Rules
- All text must be in simplified Chinese.
- Stock codes must be 6-digit strings from the company list returned by `query_industry_companies`.
- Never invent companies, segments, or financial numbers.
- Each node must have at least 2 and at most 5 companies in `companies`.
- `companies` arrays must not be empty.
- All `edges.source` and `edges.target` must match a `node.name`.
- For any numeric metric you cannot compute from provided data, use `null`.
- After persisting, summarize the analysis for the user in 2-4 sentences and mention that the graph is available on the industry-chain page.

## Example
User: "分析半导体产业链"

1. Call `query_industry_companies(industry="半导体")`.
2. Call `query_financial_data(stock_codes=["600703", "688126", "688981", ...], periods=3)`.
3. Call `search_news(keyword="半导体", days=30, limit=15)`.
4. Call `search_vector_kb(query="半导体 产业链 供应商 客户 上下游", limit=5)`.
5. Derive segments: 光刻胶, CMP抛光材料, 刻蚀设备, 晶圆制造, 芯片设计, 封装测试, 功率器件...
6. Build edges and compute metrics.
7. Call `persist_chain_analysis(industry="半导体", result={...})`.
8. Reply: "已完成半导体产业链分析，共识别 X 个环节、Y 家核心公司，结果已保存为产业链页面最新版本 vN。"
