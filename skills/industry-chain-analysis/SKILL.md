# Industry Chain Analysis Skill

## Description
Analyze the upstream and downstream supply chain of a specified industry. 
Identify representative listed companies at each node of the chain, 
compare their financial performance, and output a structured industry 
chain graph with investment insights.

## Triggers
- User asks to analyze an industry's supply chain / value chain
- User asks about upstream/downstream relationships of an industry
- User wants to understand competitive landscape within an industry chain
- Keywords: 产业链, 上下游, 供应链, 价值链, 行业分析, industry chain

## Analysis Workflow

### Step 1: Data Collection
1. Use akshare to fetch all listed companies in the target industry (申万行业分类)
2. Query PostgreSQL `stock_basic` table for company basic info
3. Query PostgreSQL for latest financial data: `income_statement`, `balance_sheet` (most recent 3 reporting periods)
4. Search Elasticsearch `announcements` index for industry-related news in the last 30 days
5. Search Milvus `financial_doc_chunks` collection for content about "{industry_name} 产业链 供应商 客户 上下游 业务构成"
6. Search Milvus `research_doc_chunks` collection for analyst reports about the industry

### Step 2: Chain Structure Identification
1. Based on retrieved reports and company business descriptions, identify the upstream, midstream, and downstream segments
2. For each segment, identify 3-5 representative listed companies
3. Determine supply-demand relationships and technology dependencies between segments
4. Identify any missing links or external dependencies in the chain

### Step 3: Financial Comparison
1. Compare gross margins across segments (average and range)
2. Calculate revenue growth rates (YoY, last 2 years) for each segment
3. Calculate R&D expense as % of revenue for each segment
4. Analyze bargaining power indicators:
   - Accounts receivable turnover
   - Prepayments received / revenue ratio
   - Inventory turnover

### Step 4: Value Distribution & Bottleneck Analysis
1. Map the value distribution across the chain (gross margin contribution per segment)
2. Identify segments with the highest profit concentration
3. Identify production bottlenecks or technology choke points
4. Extract recent breakthroughs and capacity expansion signals from news/announcements

### Step 5: Output Generation
Generate a structured analysis result in the following JSON format:

```json
{
  "industry": "半导体",
  "analyzed_at": "2026-07-05T10:00:00Z",
  "nodes": [
    {
      "name": "硅材料/衬底",
      "type": "upstream",
      "description": "高纯度硅片、碳化硅衬底制造",
      "companies": [
        {"code": "600703", "name": "三安光电", "market_cap_billion": 850},
        {"code": "688126", "name": "沪硅产业", "market_cap_billion": 520}
      ],
      "avg_gross_margin": 25.3,
      "avg_revenue_growth_2y": 15.2,
      "avg_rd_ratio": 8.5,
      "bargaining_power_score": 6.5,
      "bottleneck_indicators": ["高端硅片依赖进口", "扩产周期长"],
      "recent_breakthroughs": ["国产12英寸硅片良率突破80%"]
    }
  ],
  "edges": [
    {
      "source": "硅材料/衬底",
      "target": "晶圆制造",
      "relation": "核心原材料供应",
      "strength": 95,
      "description": "硅片是晶圆制造的不可替代原材料",
      "criticality": "high"
    }
  ],
  "summary": "半导体产业链呈现上游集中、中游资本密集、下游分散的格局...",
  "value_distribution": {
    "highest_margin_segment": "芯片设计",
    "highest_margin_value": 45.2,
    "lowest_margin_segment": "封装测试",
    "lowest_margin_value": 18.5
  },
  "opportunities": [
    {
      "title": "半导体设备国产替代加速",
      "description": "受外部限制影响，国内晶圆厂加速导入国产设备...",
      "related_segment": "设备制造",
      "confidence": "high"
    }
  ],
  "risks": [
    {
      "title": "先进制程技术封锁",
      "description": "EUV光刻机持续受限，影响先进制程扩产...",
      "related_segment": "晶圆制造",
      "severity": "high"
    }
  ],
  "key_companies_summary": [
    {"code": "688981", "name": "中芯国际", "chain_position": "晶圆制造", "score": 85},
    {"code": "603501", "name": "韦尔股份", "chain_position": "芯片设计", "score": 82}
  ]
}
```

## Available Tools
- Python 3 with akshare, pandas - for data fetching and computation
- PostgreSQL via SQL queries - for structured financial data
- Elasticsearch via HTTP API - for news/announcement search
- Milvus via pymilvus - for vector similarity search in document knowledge base
- File system read/write - for intermediate results and final output

## Expected Output
Save the analysis result to `data/analysis/{industry_slug}/chain_{date}.json`.
Also write a human-readable summary to `data/analysis/{industry_slug}/summary_{date}.md`.

## Notes
- Use simplified Chinese for all descriptions and summaries
- Stock codes should be 6-digit strings
- Financial figures in 亿元 (CNY hundred million)
- Always cite data sources for each factual claim
