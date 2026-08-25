---
name: financial-health-check
description: 个股财务体检：计算核心财务比率（ROE、毛利率、资产负债率、现金流等）、与行业对比并标记风险项，产出结构化健康报告。当用户要求"财务体检/财务分析"或询问具体财务指标时使用。
---

# Financial Health Check Skill

## Description
Perform a comprehensive financial health check on a single company.
Calculate key financial ratios, compare with industry peers, and flag risks.
Output a radar-chart-ready health score and a structured report.

## Triggers
- User asks to evaluate a company's financial health
- User wants a 财务体检 or financial checkup
- User asks about specific financial ratios (ROE, debt ratio, etc.)
- Keywords: 财务分析, 体检, ROE, 毛利率, 资产负债率, financial health

## Analysis Workflow

### Step 1: Data Retrieval
1. Query PostgreSQL for 5 years of financial data from:
   - `income_statement`: revenue, costs, profit, EPS
   - `balance_sheet`: assets, liabilities, equity, goodwill
   - `cash_flow_statement`: operating/investing/financing cash flows
2. Get industry peers (same 申万三级行业, top 10 by market cap)
3. Get the same financial data for peers (latest period)

### Step 2: Ratio Calculation
Calculate the following ratios for the target company:

**Profitability:**
- ROE (净资产收益率) = net_profit / total_equity
- Gross Margin (毛利率) = (revenue - cost) / revenue
- Net Margin (净利率) = net_profit / revenue
- ROA (总资产收益率) = net_profit / total_assets

**Growth:**
- Revenue Growth (营收增速) YoY
- Net Profit Growth (净利润增速) YoY
- EPS Growth (每股收益增速)

**Financial Health:**
- Debt-to-Asset Ratio (资产负债率) = total_liabilities / total_assets
- Current Ratio (流动比率) = current_assets / current_liabilities
- Quick Ratio (速动比率) = (current_assets - inventory) / current_liabilities

**Efficiency:**
- Asset Turnover (总资产周转率) = revenue / total_assets
- Inventory Turnover (存货周转率)
- Receivables Turnover (应收账款周转率)

**Cash Flow:**
- Operating CF / Revenue
- Free Cash Flow = operating_cf - capex

### Step 3: Trend Analysis
For each key ratio, analyze 5-year trend:
- Improving ↑ / Stable → / Deteriorating ↓
- Flag any YoY change > 20% as "abnormal"
- For abnormal changes, search announcements/news for explanations

### Step 4: Industry Comparison
Compare target vs. industry median/quartiles:
- Generate radar chart data (normalized to 0-100)
- Radar axes: Profitability, Growth, Debt Health, Operational Efficiency, Cash Flow
- Calculate percentile rank for each axis

### Step 5: Risk Detection
Flag warnings if:
- Receivables / Revenue > 30% for 2+ consecutive years
- Inventory / Revenue shows abnormal increase
- Goodwill / Net Assets > 30%
- Operating CF consistently < Net Profit (earnings quality concern)
- Debt-to-Asset > 70% for non-financial companies
- Revenue growth > 50% without corresponding CF growth

### Step 6: Output
```json
{
  "company": {"code": "000001", "name": "平安银行"},
  "analyzed_at": "2026-07-05",
  "overall_score": 72,
  "score_breakdown": {
    "profitability": 75,
    "growth": 58,
    "debt_health": 60,
    "efficiency": 70,
    "cash_flow": 68
  },
  "radar_data": {
    "labels": ["盈利能力", "成长性", "偿债能力", "运营效率", "现金流"],
    "company_values": [75, 58, 60, 70, 68],
    "industry_median": [62, 45, 55, 60, 58]
  },
  "key_ratios": {
    "roe": {"current": 12.5, "trend": "improving", "industry_median": 10.2},
    "gross_margin": {"current": 35.2, "trend": "stable", "industry_median": 32.8},
    "debt_to_asset": {"current": 62.3, "trend": "deteriorating", "industry_median": 55.0}
  },
  "trend_highlights": [
    {"metric": "ROE", "direction": "up", "detail": "从 8.2% 提升至 12.5%，连续3年改善"},
    {"metric": "资产负债率", "direction": "up", "detail": "从 55% 升至 62.3%，需关注"}
  ],
  "strengths": [
    "盈利能力持续改善，ROE领先行业",
    "营收增速高于行业平均 15%"
  ],
  "risks": [
    {"type": "应收账款高企", "severity": "medium", "detail": "应收账款/营收占比达32%"},
    {"type": "现金流质量", "severity": "medium", "detail": "经营现金流连续2年低于净利润"}
  ],
  "peer_comparison": {
    "rank_in_industry": "top_30_percent",
    "closest_peers": [
      {"code": "000002", "name": "万科A", "similarity_score": 85}
    ]
  }
}
```

## Available Tools
- PostgreSQL for financial data queries
- Python 3 with pandas/numpy for ratio calculations
- Elasticsearch for searching explanations of abnormal changes

## Expected Output
Save to `data/analysis/{stock_code}/health_check_{date}.json`

## Notes
- Use 申万2021 industry classification
- Financial data should use the most recent audited report for trailing-twelve-month calculations
- Flag data availability issues clearly
