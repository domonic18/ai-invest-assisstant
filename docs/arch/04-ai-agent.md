# AI Agent 体系设计

## 1. Agent 体系总览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AI Agent 编排层 (LangGraph)                        │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                     Supervisor Agent (调度器)                      │   │
│  │    根据用户请求，分发给对应的子 Agent，汇总输出结果                 │   │
│  └──────┬───────────────┬───────────────┬──────────────────────────┘   │
│         │               │               │                               │
│  ┌──────┴──────┐ ┌──────┴──────┐ ┌──────┴──────┐                       │
│  │ 财报分析     │ │ 研报分析     │ │ 热点追踪     │                      │
│  │ Agent        │ │ Agent        │ │ Agent        │                     │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘                       │
│         │               │               │                               │
│  ┌──────┴───────────────┴───────────────┴──────┐                       │
│  │              共享能力层                       │                       │
│  │  RAG 检索 │ 数据查询 │ 数值计算 │ 图表生成    │                      │
│  └─────────────────────────────────────────────┘                       │
└─────────────────────────────────────────────────────────────────────────┘
```

## 2. 核心 Agent 设计

### 2.1 Supervisor Agent（调度器）

```python
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolExecutor
from typing import TypedDict, Annotated, Sequence
import operator


class SupervisorState(TypedDict):
    messages: Annotated[Sequence[dict], operator.add]
    user_query: str
    industry: str                    # 目标行业
    task: str                        # 任务类型
    selected_agent: str
    agent_results: dict              # 各 Agent 结果
    final_output: str


class SupervisorAgent:
    """顶层调度 Agent：理解用户意图，分发任务"""

    SYSTEM_PROMPT = """你是一个投资分析系统的调度 Agent。
根据用户的查询，判断需要调用哪个子 Agent：
- 财报分析 Agent：涉及财务报表分析、产业链上下游分析、公司基本面
- 研报分析 Agent：涉及券商研报摘要、评级变化跟踪、行业研报
- 热点追踪 Agent：涉及新闻热点、市场情绪、资金流向异动

输出格式：{"agent": "<agent_name>", "reasoning": "<分配理由>"}
"""

    def __init__(self, llm, config: dict):
        self.llm = llm
        self.config = config
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(SupervisorState)

        workflow.add_node("route", self._route_task)
        workflow.add_node("financial_analysis", self._call_financial_agent)
        workflow.add_node("research_analysis", self._call_research_agent)
        workflow.add_node("hotspot_tracking", self._call_hotspot_agent)
        workflow.add_node("aggregate", self._aggregate_results)

        workflow.set_entry_point("route")

        workflow.add_conditional_edges(
            "route",
            lambda s: s["selected_agent"],
            {
                "financial": "financial_analysis",
                "research": "research_analysis",
                "hotspot": "hotspot_tracking"
            }
        )
        workflow.add_edge("financial_analysis", "aggregate")
        workflow.add_edge("research_analysis", "aggregate")
        workflow.add_edge("hotspot_tracking", "aggregate")
        workflow.add_edge("aggregate", END)

        return workflow.compile()
```

### 2.2 财报分析 Agent（核心）

这是系统的核心 Agent，负责对某个行业进行**上下游产业链分析**。

```python
class FinancialAnalysisAgent:
    """财报分析 Agent：产业链分析、基本面评估"""

    SYSTEM_PROMPT = """你是一个专业的产业链分析专家。
你的任务是：
1. 分析指定行业的产业链上下游关系
2. 识别各环节的核心上市公司
3. 基于财务数据分析各环节的盈利能力、竞争格局
4. 发现产业链中的瓶颈环节和高增长节点

分析框架：
- 上游：原材料供应商、设备制造商
- 中游：核心零部件、中间品制造
- 下游：终端产品、销售渠道、售后服务

对每个环节，你需要：
- 列出代表公司及其市场份额
- 分析该环节的毛利率、净利率变化趋势
- 判断该环节的议价能力（对上游/下游）
- 识别技术创新点和突破方向
"""

    def __init__(self, llm, db_session, milvus_client, es_client):
        self.llm = llm
        self.db = db_session
        self.milvus = milvus_client
        self.es = es_client

    async def analyze_industry_chain(self, industry: str) -> dict:
        """分析指定行业的产业链"""
        
        # 步骤1：RAG 检索 - 从知识库获取相关财报、研报内容
        chain_context = await self._retrieve_chain_context(industry)
        
        # 步骤2：数据库查询 - 获取行业内公司的财务数据
        financial_data = await self._query_financial_data(industry)
        
        # 步骤3：LLM 分析 - 构建产业链图谱
        chain_analysis = await self._llm_analyze(
            industry, chain_context, financial_data
        )
        
        # 步骤4：结构化输出 - 写入数据库
        await self._save_chain_to_db(chain_analysis)
        
        return chain_analysis

    async def _retrieve_chain_context(self, industry: str) -> str:
        """从知识库检索产业链相关内容"""
        
        # Milvus 向量检索 - 财报文档中关于产业链的内容
        embedding = await self.llm.embed_query(
            f"{industry} 产业链 上游 中游 下游 供应商 客户"
        )
        
        results = self.milvus.search(
            collection_name="financial_doc_chunks",
            data=[embedding],
            anns_field="embedding",
            param={"metric_type": "COSINE", "params": {"nprobe": 10}},
            limit=20,
            expr=f'industry == "{industry}"',
            output_fields=["chunk_text", "stock_code", "report_date"]
        )
        
        # Elasticsearch 关键字检索 - 公告/新闻中的产业链线索
        es_results = self.es.search(
            index="announcements",
            body={
                "query": {
                    "multi_match": {
                        "query": f"{industry} 产业链 供应商 客户 上下游",
                        "fields": ["title^3", "content"]
                    }
                },
                "size": 10
            }
        )
        
        # 整合上下文
        context = self._format_retrieval_context(results, es_results)
        return context

    async def _llm_analyze(self, industry, context, financial_data):
        """LLM 进行产业链深度分析"""
        
        prompt = f"""
{self.SYSTEM_PROMPT}

## 行业信息
目标行业：{industry}

## 检索到的上下文
{context}

## 行业内公司财务数据
{financial_data}

请输出完整的产业链分析报告，包含：
1. 产业链全景图（上游→中游→下游）
2. 各环节代表公司及财务健康度评分
3. 产业链价值分布（各环节毛利率对比）
4. 关键趋势和投资机会
5. 风险提示

输出 JSON 格式，字段包括：
- chain_nodes: [{{"name", "type": "upstream/midstream/downstream",
    "companies": [...], "avg_gross_margin": ..., "bargaining_power": ...}}]
- chain_edges: [{{"source", "target", "relation", "strength"}}]
- summary: "产业链总结"
- opportunities: ["机会1", "机会2"]
- risks: ["风险1", "风险2"]
"""
        
        response = await self.llm.chat(prompt)
        return self._parse_chain_response(response)

    async def _save_chain_to_db(self, analysis: dict):
        """将分析结果持久化到数据库"""
        async with self.db.begin():
            for node in analysis["chain_nodes"]:
                await self.db.execute("""
                    INSERT INTO industry_chain_node
                    (node_name, industry_l1, node_type, description, key_companies)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT DO NOTHING
                """, ...)
            
            for edge in analysis["chain_edges"]:
                await self.db.execute("""
                    INSERT INTO industry_chain_edge
                    (source_node_id, target_node_id, relation_type, relation_desc, strength)
                    VALUES ($1, $2, $3, $4, $5)
                """, ...)
```

### 2.3 研报分析 Agent

```python
class ResearchAnalysisAgent:
    """研报分析 Agent：提取关键观点、跟踪评级变化"""

    SYSTEM_PROMPT = """你是一个券商研报分析专家。
任务：
1. 提取研报核心观点（目标价、评级、核心逻辑）
2. 对比多家券商对同一公司的评级差异
3. 跟踪评级变化趋势
4. 识别研报中提到的行业关键趋势
"""

    async def summarize_report(self, report_id: str) -> dict:
        """单篇研报摘要"""
        # 1. 从 MinIO 获取研报 PDF
        # 2. 从 Milvus 检索研报文本切片
        # 3. LLM 生成结构化摘要
        pass

    async def track_rating_changes(self, stock_code: str) -> dict:
        """跟踪评级变化"""
        # 查询历史研报，分析评级时间序列变化
        pass

    async def consolidate_views(self, stock_code: str) -> dict:
        """整合多家券商观点"""
        # 聚合分析，识别一致预期和分歧点
        pass
```

### 2.4 热点追踪 Agent

```python
class HotspotTrackingAgent:
    """热点追踪 Agent：新闻聚类、情绪分析、异动监控"""

    SYSTEM_PROMPT = """你是一个市场热点分析专家。
任务：
1. 实时追踪个股和行业新闻
2. 对新闻进行聚类，识别热点主题
3. 分析市场情绪（积极/消极/中性）
4. 监控资金流向异动
5. 发现产业链中的新突破点
"""

    async def detect_hotspots(self, industry: str = None) -> dict:
        """检测当前热点"""
        # 1. ES 查询近期新闻
        # 2. 使用 LLM 聚类热点主题
        # 3. 情绪打分
        # 4. 关联资金流向数据
        pass

    async def find_breakthroughs(self, industry: str) -> list[dict]:
        """发现产业链突破点"""
        # 结合财报 Agent 的产业链分析结果
        # 从新闻/公告中提取技术创新信号
        # 识别产能扩张、新产品发布等关键事件
        pass
```

## 3. RAG 管道设计

```
用户查询
    │
    ▼
┌──────────────────────────────────────┐
│         查询重写 (Query Rewrite)       │
│  将自然语言查询优化为检索友好形式       │
└──────────────┬───────────────────────┘
               │
    ┌──────────┼──────────┐
    ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐
│Milvus  │ │Elastic │ │Postgre │
│向量检索 │ │全文检索 │ │结构化查询│
└───┬────┘ └───┬────┘ └───┬────┘
    │          │          │
    └──────────┼──────────┘
               ▼
┌──────────────────────────────────────┐
│         结果融合 (Fusion)             │
│  RRF (Reciprocal Rank Fusion)       │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│         上下文压缩 (Compression)       │
│  剔除冗余，保留高价值信息              │
└──────────────┬───────────────────────┘
               │
               ▼
         LLM 生成回答
```

## 4. Agent 工具集

```python
# Agent 可调用的工具
AGENT_TOOLS = [
    # 数据查询工具
    Tool("query_financial_data", "查询公司财务数据",
         func=query_financial_data),
    Tool("query_kline", "查询K线数据",
         func=query_kline),
    Tool("query_fund_flow", "查询资金流向",
         func=query_fund_flow),
    
    # 知识检索工具
    Tool("search_financial_docs", "搜索财报文档内容",
         func=search_milvus_financial),
    Tool("search_research_docs", "搜索研报文档内容",
         func=search_milvus_research),
    Tool("search_news", "搜索新闻/公告",
         func=search_elasticsearch),
    
    # 分析工具
    Tool("calculate_ratio", "计算财务比率",
         func=calculate_financial_ratio),
    Tool("compare_companies", "横向对比公司",
         func=compare_companies),
    Tool("get_industry_chain", "获取产业链结构",
         func=get_industry_chain),
    
    # 输出工具
    Tool("generate_chart", "生成图表数据",
         func=generate_chart_data),
]
```

## 5. Agent 任务编排（LangGraph 工作流）

```python
def build_industry_analysis_workflow():
    """产业链分析完整工作流"""
    
    workflow = StateGraph(IndustryAnalysisState)
    
    # 节点定义
    workflow.add_node("identify_industry", identify_target_industry)
    workflow.add_node("collect_companies", collect_industry_companies)
    workflow.add_node("analyze_financials", analyze_each_company_financials)
    workflow.add_node("build_chain", build_industry_chain_structure)
    workflow.add_node("analyze_bottleneck", analyze_chain_bottleneck)
    workflow.add_node("find_breakthroughs", find_technology_breakthroughs)
    workflow.add_node("generate_report", generate_final_report)
    
    # 流程编排
    workflow.set_entry_point("identify_industry")
    workflow.add_edge("identify_industry", "collect_companies")
    workflow.add_edge("collect_companies", "analyze_financials")
    workflow.add_edge("analyze_financials", "build_chain")
    workflow.add_edge("build_chain", "analyze_bottleneck")
    workflow.add_edge("analyze_bottleneck", "find_breakthroughs")
    workflow.add_edge("find_breakthroughs", "generate_report")
    workflow.add_edge("generate_report", END)
    
    return workflow.compile()
```
