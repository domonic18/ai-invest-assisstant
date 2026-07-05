# Research Report Summary Skill

## Description
Batch summarize broker research reports for a specified company or industry.
Extract structured opinions including ratings, target prices, core logic,
and盈利预测. Track rating changes and identify consensus vs. divergence.

## Triggers
- User asks to summarize analyst reports for a company
- User wants to compare multiple broker opinions
- User asks about rating changes for a stock
- Keywords: 研报, 评级, 目标价, 券商观点, research report, analyst rating

## Analysis Workflow

### Step 1: Report Retrieval
1. Query PostgreSQL `file_metadata` table for recent research reports on the target company (last 90 days)
2. If no direct reports found, expand search to industry-wide reports
3. From MinIO, locate the PDF files for the found reports
4. Search Milvus `research_doc_chunks` for key sections: recommendations, earnings forecasts, risk warnings

### Step 2: Multi-Broker Opinion Extraction
For each report, extract:
1. **Rating**: Buy / Overweight / Neutral / Underweight / Sell
2. **Target price** (if available)
3. **Core thesis** (2-3 sentence summary)
4. **Earnings forecast**: next 2 years revenue and net profit projections
5. **Key risks** mentioned
6. **Report date** and **analyst name**

### Step 3: Rating Change Detection
1. For each broker, find the previous report on the same company
2. Compare current vs previous rating → mark as Upgraded / Maintained / Downgraded
3. Calculate target price change percentage

### Step 4: Consensus & Divergence Analysis
1. Calculate rating distribution (Buy: X%, Neutral: Y%, Sell: Z%)
2. Calculate target price range (low - high)
3. Identify metrics where analyst forecasts diverge significantly (std > 30% of mean)

### Step 5: Output
Generate structured JSON:
```json
{
  "company": {"code": "000001", "name": "平安银行"},
  "analyzed_at": "2026-07-05T10:00:00Z",
  "report_count": 12,
  "broker_count": 8,
  "rating_distribution": {
    "buy": 6, "overweight": 3, "neutral": 2, "underweight": 1, "sell": 0
  },
  "consensus_rating": "增持",
  "target_price": {"low": 9.5, "high": 15.2, "median": 12.8, "current": 11.3},
  "upside_potential": 13.3,
  "rating_changes": [
    {"broker": "中信证券", "previous": "增持", "current": "买入", "change": "upgraded"}
  ],
  "bullish_themes": [
    "零售转型成效显著，财富管理收入快速增长",
    "不良贷款率持续下降，资产质量改善"
  ],
  "bearish_themes": [
    "净息差持续收窄，盈利能力承压"
  ],
  "key_reports": [
    {
      "broker": "中信证券",
      "rating": "买入",
      "target_price": 15.2,
      "thesis": "公司零售业务...",
      "date": "2026-06-20"
    }
  ],
  "earnings_consensus": {
    "revenue_2026": {"mean": 1850.5, "range": [1780, 1920]},
    "net_profit_2026": {"mean": 520.3, "range": [490, 550]}
  }
}
```

## Available Tools
- PostgreSQL for report metadata and historical ratings
- MinIO for PDF file access
- Milvus for vector search within report documents
- Python 3 for data processing

## Expected Output
Save to `data/analysis/{stock_code}/research_summary_{date}.json`

## Notes
- Only include reports from legitimate securities firms
- Mark ratings clearly with both Chinese and English equivalents
- Earnings forecasts in 亿元
