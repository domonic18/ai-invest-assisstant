---
name: financial-health-check
description: 个股财务体检：计算核心财务比率（ROE、毛利率、资产负债率、现金流等）、与行业对比并标记风险项，产出结构化健康报告。当用户要求"财务体检/财务分析"或询问具体财务指标时使用。
---

# 个股财务体检

## 描述
对单家公司进行全面的财务健康检查。计算关键财务比率，与行业同业对比，标记风险项，输出可用于雷达图的健康评分与结构化报告。

## 触发条件
- 用户要求评估某公司的财务健康状况
- 用户想要"财务体检"或财务检查
- 用户询问具体财务比率（ROE、资产负债率等）
- 关键词：财务分析、体检、ROE、毛利率、资产负债率、financial health

## 分析流程

### 步骤 1：数据获取
1. 从 PostgreSQL 查询 5 年财务数据：
   - `income_statement`：营业收入、成本、利润、EPS
   - `balance_sheet`：资产、负债、权益、商誉
   - `cash_flow_statement`：经营/投资/筹资现金流
2. 获取行业可比公司（相同申万三级行业，按市值取前 10）
3. 获取可比公司同期财务数据（最新报告期）

### 步骤 2：比率计算
为目标公司计算以下比率：

**盈利能力：**
- ROE（净资产收益率） = 净利润 / 股东权益
- 毛利率 =（营业收入 - 营业成本）/ 营业收入
- 净利率 = 净利润 / 营业收入
- ROA（总资产收益率） = 净利润 / 总资产

**成长性：**
- 营业收入同比增长
- 净利润同比增长
- EPS 同比增长

**财务健康：**
- 资产负债率 = 总负债 / 总资产
- 流动比率 = 流动资产 / 流动负债
- 速动比率 =（流动资产 - 存货）/ 流动负债

**运营效率：**
- 总资产周转率 = 营业收入 / 总资产
- 存货周转率
- 应收账款周转率

**现金流：**
- 经营现金流 / 营业收入
- 自由现金流 = 经营现金流 - 资本开支

### 步骤 3：趋势分析
对每项关键比率分析 5 年趋势：
- 改善 ↑ / 稳定 → / 恶化 ↓
- 同比变化超过 20% 标记为"异常"
- 对异常变化搜索公告/新闻寻找解释

### 步骤 4：行业对比
将目标公司与行业中位数/四分位对比：
- 生成雷达图数据（归一化到 0-100）
- 雷达维度：盈利能力、成长性、偿债能力、运营效率、现金流
- 计算每个维度的分位排名

### 步骤 5：风险检测
在以下情况标记风险：
- 应收账款 / 营业收入 > 30% 且持续 2 年以上
- 存货 / 营业收入异常上升
- 商誉 / 净资产 > 30%
- 经营现金流持续低于净利润（盈利质量存疑）
- 非金融公司资产负债率 > 70%
- 营收增长 > 50% 但现金流未同步增长

### 步骤 6：输出
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

## 可用工具
- PostgreSQL：财务数据查询
- Python 3 + pandas/numpy：比率计算
- Elasticsearch：搜索异常变化的解释

## 预期输出
保存到 `data/analysis/{stock_code}/health_check_{date}.json`

## 备注
- 使用申万 2021 行业分类
- 财务数据应优先使用最近一期审计报告，用于滚动十二个月计算
- 对数据缺失情况明确标注
