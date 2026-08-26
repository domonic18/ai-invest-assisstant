---
name: research-summary
description: 研报观点汇总：批量提炼指定公司或行业的券商研报，结构化提取评级、目标价、核心逻辑与盈利预测，识别共识与分歧。当用户要求"总结研报/对比券商观点/评级变化"时使用。
---

# 研报观点汇总

## 描述
批量总结指定公司或行业的券商研报，结构化提取评级、目标价、核心逻辑与盈利预测，跟踪评级变化并识别共识与分歧。

## 触发条件
- 用户要求总结某公司研报
- 用户希望对比多家券商观点
- 用户询问某股票评级变化
- 关键词：研报、评级、目标价、券商观点、research report、analyst rating

## 分析流程

### 步骤 1：研报检索
1. 查询 PostgreSQL `file_metadata` 表，获取目标公司最近 90 天研报
2. 若未找到直接研报，扩展到行业研报
3. 从 MinIO 定位找到研报的 PDF 文件
4. 在 Milvus `research_doc_chunks` 中搜索关键章节：评级、盈利预测、风险提示

### 步骤 2：多券商观点提取
对每篇研报提取：
1. **评级**：买入 / 增持 / 中性 / 减持 / 卖出
2. **目标价**（如有）
3. **核心逻辑**（2-3 句话总结）
4. **盈利预测**：未来 2 年营业收入与净利润预测
5. **提到的关键风险**
6. **报告日期**与**分析师姓名**

### 步骤 3：评级变化检测
1. 对每家券商，查找同公司上一篇研报
2. 对比当前与上次评级 → 标记上调 / 维持 / 下调
3. 计算目标价变化百分比

### 步骤 4：共识与分歧分析
1. 计算评级分布（买入：X%，中性：Y%，卖出：Z%）
2. 计算目标价区间（最低 - 最高）
3. 识别分析师预测分歧显著的指标（标准差 > 均值 30%）

### 步骤 5：输出
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

## 可用工具
- PostgreSQL：研报元数据与历史评级
- MinIO：PDF 文件访问
- Milvus：研报文档向量化检索
- Python 3：数据处理

## 预期输出
保存到 `data/analysis/{stock_code}/research_summary_{date}.json`

## 备注
- 仅使用正规券商研报
- 评级同时标注中英文对应关系
- 盈利预测单位为亿元
