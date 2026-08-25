---
name: hotspot-detection
description: 市场热点检测：聚合近期新闻、分析情绪与资金流、交叉产业链突破信号，输出热点板块排行与可操作洞察。当用户问"今天什么热门/热点/资金流向哪/市场情绪/异动"时使用。
---

# Hotspot Detection Skill

## Description
Track real-time market hotspots by aggregating news, analyzing sentiment,
cross-referencing capital flows, and identifying supply chain breakthroughs.
Output a comprehensive hotspot dashboard with actionable insights.

## Triggers
- User asks what's hot in the market today
- User wants to know trending topics or sectors
- User asks about market sentiment or fund flow anomalies
- Keywords: 热点, 热门, 资金流向, 情绪, 异动, hotspot, trending

## Analysis Workflow

### Step 1: News Aggregation
1. Query Elasticsearch `announcements` index for news in the last 24 hours (limit 200)
2. Group by industry tags and keyword clusters
3. Calculate hotness score = news_count * recency_weight * importance_weight
4. Identify top 10 hot topics

### Step 2: Sentiment Analysis
For each hot topic cluster:
1. Classify each article as Positive / Negative / Neutral
2. Calculate sentiment ratio (positive / total)
3. Extract key positive drivers and negative concerns
4. Assign overall sentiment score (-1.0 to +1.0)

### Step 3: Capital Flow Cross-Reference
1. Query PostgreSQL `fund_flow` for today's sector capital flows
2. Match hot topics with capital flow sectors
3. Mark sectors with "资金+情绪共振" (both hot news AND significant inflows)
4. Mark sectors with "背离" (hot news but OUTflows, or cold news but INflows)

### Step 4: Supply Chain Breakthrough Detection
Scan hot news for breakthrough signals:
- Technology: "突破" "量产" "首发" "自主可控" "国产替代"
- Capacity: "扩产" "投产" "产能" "新产线"
- Policy: "政策" "补贴" "规划" "支持"
- Product: "新品" "发布" "通过认证"

For each breakthrough:
1. Determine which industry chain segment it affects
2. Identify affected listed companies
3. Estimate impact magnitude (high/medium/low)
4. Write a one-sentence impact summary

### Step 5: Output
```json
{
  "analyzed_at": "2026-07-05T15:30:00Z",
  "hot_topics": [
    {
      "topic": "AI芯片",
      "hotness_score": 95,
      "news_count": 28,
      "sentiment": 0.72,
      "sentiment_label": "积极",
      "capital_flow_match": true,
      "sector_net_inflow_billion": 28.5,
      "key_drivers": ["英伟达发布新一代GPU", "国产AI芯片出货量翻倍"],
      "related_companies": ["688256", "688041", "688047"]
    }
  ],
  "sentiment_cross_section": {
    "most_positive_sector": "半导体",
    "most_negative_sector": "房地产",
    "divergence_alerts": [
      {"sector": "新能源", "sentiment": "积极", "capital_flow": "净流出", "alert": "情绪与资金背离"}
    ]
  },
  "capital_flow_top": {
    "inflow_top3": [
      {"sector": "半导体", "net_inflow": 28.5},
      {"sector": "AI概念", "net_inflow": 22.1},
      {"sector": "医药", "net_inflow": 18.3}
    ],
    "outflow_top3": [
      {"sector": "房地产", "net_outflow": 15.2},
      {"sector": "银行", "net_outflow": 12.8}
    ]
  },
  "breakthroughs": [
    {
      "event": "国产5nm刻蚀机通过验证",
      "sector": "半导体设备",
      "chain_position": "上游-设备制造",
      "impact_level": "high",
      "affected_companies": ["002371", "688012"],
      "summary": "国产刻蚀设备突破5nm制程，将加速晶圆厂国产设备导入"
    }
  ],
  "summary": "今日市场热点集中在AI芯片和半导体设备..."
}
```

## Available Tools
- Elasticsearch for news search and aggregation
- PostgreSQL for fund flow data
- Python 3 for clustering and sentiment scoring
- Milvus for matching breakthroughs with company contexts

## Expected Output
Save to `data/analysis/hotspot/hotspot_{date}.json`
Also generate a Markdown summary for frontend display.

## Notes
- Run automatically every 30 minutes during trading hours
- Cross-reference with official exchange announcements for verification
- Flag unverified rumors as "待确认"
