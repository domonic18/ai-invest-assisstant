# Supply Chain Breakthrough Detection Skill

## Description
Detect and analyze technology breakthroughs, capacity expansions, and 
regulatory changes within industry supply chains. Identify which chain 
segments are undergoing rapid change and which companies benefit most.

## Triggers
- User asks about breakthrough opportunities in a supply chain
- User wants to find investment opportunities around technology advances
- User asks "what's new" or "what's changing" in an industry
- Keywords: 突破, 突破点, 国产替代, 技术突破, 产能扩张, 政策利好

## Analysis Workflow

### Step 1: Signal Detection
Search for breakthrough signals across multiple sources:
1. Elasticsearch `announcements`: search for keywords ["技术突破", "量产", "自主可控", "国产替代", "全球首发", "通过认证"]
2. Elasticsearch `announcements`: search for ["扩产", "投产", "产能", "新产线", "产能利用率"]
3. Elasticsearch `announcements`: search for ["政策", "补贴", "产业规划", "专项资金", "支持"]
4. PostgreSQL: check R&D expense growth anomalies (sudden spike may indicate new product development)
5. PostgreSQL: check capital expenditure anomalies (sudden spike may indicate capacity expansion)

### Step 2: Event Classification
For each detected signal, classify:
1. **Event type**: Technology Breakthrough / Capacity Expansion / Policy Support / Product Launch / Certification
2. **Industry**: Map to 申万 industry classification
3. **Chain position**: upstream / midstream / downstream
4. **Time horizon**: Short-term impact (0-3 months) / Medium-term (3-12 months) / Long-term (>12 months)
5. **Certainty level**: Confirmed / High Probability / Speculative

### Step 3: Impact Analysis
For each significant event:
1. Identify directly affected companies (the company making the breakthrough AND its competitors)
2. Identify indirectly affected companies (suppliers, customers in the chain)
3. Estimate revenue impact (%) for affected companies
4. Determine competitive landscape changes (will this shift market share?)
5. Cross-reference with recent stock price movement to see if market has priced it in

### Step 4: Trend Synthesis
1. Group related breakthroughs into "themes" (e.g., "AI chip localization", "solid-state battery")
2. For each theme, generate a timeline of key milestones
3. Assess overall theme maturity (early stage / acceleration / maturation)
4. Identify the "most investable" theme based on certainty + impact + timing

### Step 5: Output
```json
{
  "analyzed_at": "2026-07-05",
  "period": "last_30_days",
  "events": [
    {
      "event_id": "evt_001",
      "title": "中微公司5nm刻蚀机通过台积电验证",
      "type": "technology_breakthrough",
      "industry": "半导体设备",
      "chain_position": "上游-设备制造",
      "date": "2026-07-02",
      "certainty": "confirmed",
      "time_horizon": "medium_term",
      "directly_affected": [
        {"code": "688012", "name": "中微公司", "impact": "high_positive", "reason": "产品线扩充，打开5nm市场"}
      ],
      "indirectly_affected": [
        {"code": "002371", "name": "北方华创", "impact": "medium_negative", "reason": "竞争加剧"},
        {"code": "688981", "name": "中芯国际", "impact": "medium_positive", "reason": "国产设备选择增加，降低对进口依赖"}
      ],
      "market_priced_in": "partially",
      "stock_reaction": "+8.5% on announcement day"
    }
  ],
  "themes": [
    {
      "theme": "半导体设备国产替代",
      "maturity": "acceleration",
      "key_milestones": [
        {"date": "2025-Q3", "event": "28nm全产线设备国产化验证通过"},
        {"date": "2026-Q1", "event": "14nm刻蚀机交付"},
        {"date": "2026-Q2", "event": "5nm刻蚀机通过验证"}
      ],
      "investability_score": 92,
      "investability_rationale": "政策明确支持，技术突破持续推进，下游需求确定"
    }
  ],
  "actionable_insights": [
    {
      "type": "opportunity",
      "title": "半导体设备板块进入业绩兑现期",
      "description": "多家设备公司Q2订单环比增长超50%，国产替代从主题进入业绩驱动阶段",
      "suggested_companies": ["688012", "002371", "688200"],
      "confidence": "high"
    }
  ],
  "summary": "过去30天，半导体设备产业链出现多个重大突破..."
}
```

## Available Tools
- Elasticsearch for event detection in news/announcements
- PostgreSQL for R&D and CapEx anomaly detection
- Python 3 for data processing and classification
- akshare for recent stock price data

## Expected Output
Save to `data/analysis/breakthroughs/breakthroughs_{date}.json`

## Notes
- Prioritize events from official company announcements over rumors
- Clearly label speculative events
- Update the breakthrough database weekly
