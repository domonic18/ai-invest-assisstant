---
name: chain-breakthrough
description: 供应链突破检测：基于财报与财务数据，识别产业链中的技术突破、产能扩张与政策利好信号，定位受益环节与公司。当用户问某行业"突破点/国产替代/技术突破/产能扩张/政策利好"时使用。
---

# 供应链突破检测

## 描述
以财报为核心依据，检测并分析产业链中的技术突破、产能扩张与政策变化信号。通过财报摘要、财务指标异常与研报观点交叉验证，识别正在快速变化的环节以及最受益的上市公司。

## 触发条件
- 用户询问某产业链的突破机会
- 用户希望围绕技术进步寻找投资机会
- 用户问某行业的国产替代、技术突破、产能扩张或政策利好
- 关键词：突破、突破点、国产替代、技术突破、产能扩张、政策利好

## 分析流程

### 步骤 1：确定目标公司与财报覆盖
1. 调用 `query_industry_companies(industry=...)` 获取目标行业上市公司清单。
2. 对代表性公司调用 `query_financial_reports(stock_code=...)` 查询已存在的财报。
3. 若缺少近期年报（annual）或三季报（q3），调用 `download_financial_reports(stock_code=..., report_types=["annual", "q3"])` 触发异步下载。

`download_financial_reports` 是异步任务，返回 `log_id` 与 `status`。若触发下载，应告知用户部分财报正在补充，并基于已可用数据继续分析。

### 步骤 2：财报摘要扫描
对关键公司的财报调用 `summarize_financial_report(report_id=...)`，重点提取以下信号：
- **技术突破**：新产品、新工艺、制程进展、通过客户验证、专利/认证进展
- **产能扩张**：新建产线、扩产项目、产能利用率、资本开支增加
- **政策利好**：政府补助、税收优惠、专项补贴、产业基金支持
- **国产替代**：核心零部件自研、进口替代、客户导入进展

### 步骤 3：财务指标异常检测
调用 `query_financial_data(stock_codes=[...], periods=3)`，重点关注：
- 研发费用同比大幅上升（可能预示新产品/技术投入）
- 资本开支 / 在建工程异常增长（可能预示产能扩张）
- 毛利率阶段性提升（可能预示技术突破或产品结构优化）
- 应收账款周转变化（可能反映订单/客户结构变化）

对异常指标，回到对应财报摘要寻找解释，避免误判。

### 步骤 4：事件分类
对每条检测到的信号，分类如下：
1. **事件类型**：技术突破 / 产能扩张 / 政策支持 / 产品发布 / 资质认证
2. **行业**：映射到申万行业分类
3. **产业链位置**：upstream / midstream / downstream
4. **影响周期**：短期（0-3 个月）/ 中期（3-12 个月）/ 长期（>12 个月）
5. **确定性**：已确认 / 高概率 / 推测

### 步骤 5：影响分析
对每项重大事件：
1. 识别直接受影响的公司（取得突破的公司及其竞争对手）
2. 识别间接受影响的公司（产业链上下游的供应商、客户）
3. 估算收入影响（%）
4. 判断竞争格局变化（是否会改变市场份额）
5. 可调用 `search_vector_kb(query=..., limit=5)` 检索分析师研报，验证市场观点与预期

### 步骤 6：主题归纳
1. 将相关突破归纳为"主题"（例如"AI 芯片国产替代"、"固态电池"）
2. 为每个主题生成关键里程碑时间线
3. 评估主题整体成熟度（早期 / 加速 / 成熟）
4. 基于确定性 + 影响 + 时点，识别"最具投资价值的主题"

### 步骤 7：输出
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
  "summary": "基于财报分析，过去一段时间半导体设备产业链出现多个重大突破..."
}
```

## 可用工具
- `query_industry_companies(industry, limit=150)`: 按行业名称查询上市公司清单。
- `query_financial_reports(stock_code, report_type, start_date, end_date)`: 查询已存在的财报列表。
- `download_financial_reports(stock_code, report_types, start_date, end_date)`: 触发财报异步采集。
- `query_financial_data(stock_codes, periods=3)`: 批量查询财务指标，用于异常检测。
- `summarize_financial_report(report_id)`: 获取单篇财报摘要，提取突破信号。
- `search_vector_kb(query, limit=5)`: 检索研报知识库片段，用于交叉验证观点。
- Python 3：数据处理与分类

## 预期输出
保存到 `data/analysis/breakthroughs/breakthroughs_{date}.json`

## 备注
- 分析必须以财报与财务数据为准，避免依赖市场传闻
- 对推测性事件明确标注
- 每周基于最新财报更新突破数据库
