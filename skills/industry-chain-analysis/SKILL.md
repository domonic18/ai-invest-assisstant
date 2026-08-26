---
name: industry-chain-analysis
description: 产业链分析：拆解指定行业的上下游结构，识别各环节代表上市公司并对比财务表现与竞争格局，产出结构化产业链分析与投资观点。当用户要求产业链体检/上下游/供应链/价值链分析时使用。
allowed-tools: query_industry_companies, query_financial_reports, download_financial_reports, query_financial_data, summarize_financial_report, search_vector_kb, persist_chain_analysis
---

# 产业链分析

## 描述
以财报为核心依据，分析指定行业的上下游供应链。识别产业链各节点上的代表性上市公司，对比其财务表现，输出结构化产业链图谱与投资观点。

## 触发条件
- 用户要求分析某行业的供应链/价值链
- 用户询问某行业上下游关系
- 用户希望理解产业链内竞争格局
- 关键词：产业链、上下游、供应链、价值链、行业分析、industry chain

## 输出 Schema
必须生成符合 `ChainAnalysisResult` schema 的 JSON 对象，顶层字段如下：

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
- `name`: str，环节名称（具体细分产品/材料/设备/应用领域）
- `type`: str，取值 upstream / midstream / downstream
- `description`: str，不超过 60 字
- `companies`: list of { `code`: 6 位股票代码, `name`: 公司名称 }
- `avg_gross_margin`: float | null，毛利率百分比数值，如 25.3
- `revenue_growth`: float | null，营收同比百分比数值
- `rd_ratio`: float | null，研发占比百分比数值
- `bargaining_power`: float | null，0-100 评分
- `localization_rate`: float | null，0-100 国产化率估计
- `tech_barrier`: "high" | "medium" | "low" | null
- `bottleneck_indicators`: list[str]，瓶颈/卡脖子因素
- `recent_breakthroughs`: list[str]，近期突破/扩产信号

### Edge schema
- `source`: str，起点环节名称（必须匹配某个 node.name）
- `target`: str，终点环节名称（必须匹配某个 node.name）
- `relation`: str，供应/委托/需求关系描述
- `strength`: int，0-100 关联强度
- `description`: str，关系补充说明
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
- `code`: str，6 位股票代码
- `name`: str
- `chain_position`: str | null
- `score`: float | null，0-100

## 可用工具
- `query_industry_companies(industry, limit=150)`: 按行业名称查询上市公司清单，返回股票代码、名称、二级/三级行业、经营范围。
- `query_financial_reports(stock_code, report_type, start_date, end_date)`: 查询系统中已存在的财报列表，返回报告 ID、类型、报告期、是否有 PDF/摘要等。
- `download_financial_reports(stock_code, report_types, start_date, end_date)`: 触发指定股票的财报采集任务（异步）。当系统中缺少所需财报时调用。
- `query_financial_data(stock_codes, periods=3)`: 批量查询公司核心财务指标：毛利率、营收同比、研发占比、应收周转。
- `summarize_financial_report(report_id)`: 获取单篇财报的 AI 摘要，用于从财报正文中提取主营业务、产品构成、上下游关系、扩产计划、风险提示等定性信息。
- `search_vector_kb(query, limit=5)`: 检索研报/年报知识库片段，用于补充分析师对产业链的观点。
- `persist_chain_analysis(industry, result)`: 将最终符合 schema 的 JSON 结果持久化到数据库，生成新版本并在产业链页面展示。

## 分析流程

### 步骤 1：收集公司清单
调用 `query_industry_companies(industry=...)` 获取目标行业全部上市公司。

### 步骤 2：收集并确保财报可用
从公司清单中选取最多 30 家代表性公司（优先选择经营范围与行业明确相关的公司）。对每家公司：
1. 调用 `query_financial_reports(stock_code=...)` 查询已存在的财报。
2. 若缺少最近一期年报（annual）或三季报（q3），调用 `download_financial_reports(stock_code=..., report_types=["annual", "q3"])` 触发下载。
3. 对关键公司的财报调用 `summarize_financial_report(report_id=...)`，提取主营业务、产品/服务、上下游客户与供应商、产能扩张、研发投入、国产替代进展等信息。

`download_financial_reports` 是异步任务，返回 `log_id` 与 `status`。若触发下载，可告知用户部分财报正在补充；分析应优先使用已可用的财报数据，不得因等待下载而编造数据。

### 步骤 3：收集财务指标
调用 `query_financial_data(stock_codes=[...], periods=3)` 获取毛利率、营收同比、研发占比、应收周转等核心指标。

### 步骤 4：补充研报观点（可选）
调用 `search_vector_kb(query=..., limit=5)` 检索分析师研报片段，补充对产业链结构、竞争格局、技术趋势的判断。推荐查询：
- `{industry} 产业链 供应商 客户 上下游`
- `{industry} 主营业务 经营范围 竞争格局`

### 步骤 5：自下而上归纳环节
根据财报摘要中的经营范围、产品构成与财务证据，将公司聚类为具体环节。规则：
- 环节名称必须是具体产品、材料、设备或应用领域。
- 禁止过于宽泛："半导体材料"、"设备制造"、"下游应用"
- 良好示例："光刻胶"、"CMP 抛光材料"、"刻蚀设备"、"功率器件"
- 环节总数通常 15-25 个，除非行业本身很窄，否则不少于 10 个。

### 步骤 6：划分上中下游
为每个环节指定 `type`：
- `upstream`：原材料、零部件、设备
- `midstream`：制造、集成、代工
- `downstream`：应用、终端、渠道

基于供应/委托/需求关系在环节之间构建 `edges`。每条边的 source/target 必须引用已存在的 node 名称。

### 步骤 7：计算环节级指标
对每个环节，根据所属公司财务指标计算平均值。若某环节无财务数据，使用 `null`，不得编造数字。

### 步骤 8：识别核心公司
在整条产业链中选取至少 3 家最值得关注的公司，从财务健康度、产业链位置、成长潜力等维度给出 0-100 的综合评分。

### 步骤 9：识别机会与风险
基于财报证据与财务数据，生成 3-6 条机会与 3-6 条风险。适用时填写 `confidence`/`severity` 与 `related_segment`。

### 步骤 10：持久化结果
构造最终 JSON 对象并调用 `persist_chain_analysis(industry=..., result=...)`。工具会保存结果并返回 `version_id`、`version_no`、`status`。

## 规则
- 所有文本使用简体中文。
- 股票代码必须是 `query_industry_companies` 返回的公司清单中的 6 位字符串。
- 分析必须以财报数据与财报摘要为准；不得虚构公司、环节或财务数字。
- 每个 node 的 `companies` 至少 2 家、最多 5 家，且不能为空。
- 所有 `edges.source` 与 `edges.target` 必须与某个 `node.name` 匹配。
- 无法从提供的数据计算出的数值指标统一使用 `null`。
- 持久化完成后，用 2-4 句话向用户总结分析结论，并告知图谱已在产业链页面展示。
- **进度反馈**：本 Skill 涉及多次工具调用，分析过程中请在每次开始新阶段前用 1-2 句 assistant 正文告知用户当前进展（例如“已获取半导体行业上市公司清单，接下来读取关键财报摘要……”），避免用户只看到工具调用而不知道进行到哪一步。

## 示例
用户："分析半导体产业链"

1. 调用 `query_industry_companies(industry="半导体")`。
2. 对代表性公司调用 `query_financial_reports(stock_code="688981")`、`download_financial_reports(stock_code="688981", report_types=["annual", "q3"])` 等，确保财报可用。
3. 对关键财报调用 `summarize_financial_report(report_id=...)` 提取业务与上下游信息。
4. 调用 `query_financial_data(stock_codes=["600703", "688126", "688981", ...], periods=3)`。
5. 调用 `search_vector_kb(query="半导体 产业链 供应商 客户 上下游", limit=5)`。
6. 归纳环节：光刻胶、CMP 抛光材料、刻蚀设备、晶圆制造、芯片设计、封装测试、功率器件……
7. 构建边并计算指标。
8. 调用 `persist_chain_analysis(industry="半导体", result={...})`。
9. 回复："已完成半导体产业链分析，共识别 X 个环节、Y 家核心公司，结果已保存为产业链页面最新版本 vN。"
