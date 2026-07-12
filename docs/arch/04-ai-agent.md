# AI Agent 体系设计

## 1. Agent 体系总览

### 1.1 核心设计目标

- **配置驱动**：Agent 角色、Skill 方法论、系统提示词全部通过 `backend/app/prompts/` 下的 YAML 文件定义，不在代码中硬编码。
- **Skill 与代码解耦**：新增分析能力只需新增 YAML 提示词文件 + Skill 目录，无需改动核心 Agent 代码。
- **多 LLM 支持**：通过统一抽象层支持 OpenAI、Anthropic 及兼容 OpenAI 协议的模型。
- **工具标准化**：内部数据工具统一通过 MCP 协议暴露，既可被 Agent 调用，也可被外部 AI 工具调用。
- **类型安全**：输出结果使用 Pydantic 模型校验，确保 API 返回结构化数据。

### 1.2 架构全景

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AI Agent 编排层                                   │
│              （PydanticAI / OpenAI Agents SDK）                          │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                     Supervisor Agent（调度器）                    │   │
│  │    根据用户请求，匹配对应的 Skill/子 Agent，汇总输出结果           │   │
│  └──────┬───────────────┬───────────────┬──────────────────────────┘   │
│         │               │               │                               │
│  ┌──────┴──────┐ ┌──────┴──────┐ ┌──────┴──────┐                       │
│  │ 产业链分析   │ │ 研报摘要     │ │ 热点追踪     │                      │
│  │ Agent        │ │ Agent        │ │ Agent        │                     │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘                       │
│         │               │               │                               │
│  ┌──────┴───────────────┴───────────────┴──────┐                       │
│  │              共享能力层                       │                       │
│  │  RAG 检索 │ 数据查询 │ 数值计算 │ 图表生成    │                      │
│  └─────────────────────────────────────────────┘                       │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.3 技术选型

| 层次 | 技术 | 说明 |
|------|------|------|
| **Agent SDK** | PydanticAI（主选）/ OpenAI Agents SDK（备选） | Python 原生，类型安全，支持多 LLM 与 MCP |
| **提示词管理** | YAML 文件 | `backend/app/prompts/` 统一管理，热加载 |
| **Skill 定义** | SKILL.md + prompts YAML | Skill 业务描述用 Markdown，提示词用 YAML |
| **工具协议** | MCP | 内部/外部工具统一标准 |
| **模型路由** | 统一 LLM Router | 支持 OpenAI / Anthropic / 兼容端点 |
| **输出校验** | Pydantic | 结构化输出、API 契约 |

## 2. 为什么不用 Codex CLI / LangGraph

| 方案 | 问题 |
|------|------|
| **Codex CLI** | 黑盒执行、厂商锁定、无法嵌入 FastAPI、无状态管理 |
| **LangGraph** | 能力完整但偏重，分析类任务不需要复杂的图编排；学习成本高 |

**本方案选择**：用轻量的 Python Agent SDK（PydanticAI）作为执行引擎，用 YAML 文件管理提示词，既保留可控性，又避免过度复杂。

## 3. 提示词与配置管理

### 3.1 目录结构

```
backend/
└── app/
    ├── prompts/                          # 提示词与 Agent 配置（YAML）
    │   ├── agents/                       # Agent 角色定义
    │   │   ├── supervisor.yaml           # 顶层调度 Agent
    │   │   ├── chain_analyst.yaml        # 产业链分析 Agent
    │   │   ├── research_analyst.yaml     # 研报分析 Agent
    │   │   ├── hotspot_analyst.yaml      # 热点追踪 Agent
    │   │   └── financial_analyst.yaml    # 财务体检 Agent
    │   └── skills/                       # Skill 提示词
    │       ├── industry-chain-analysis.yaml
    │       ├── research-summary.yaml
    │       ├── hotspot-detection.yaml
    │       ├── financial-health-check.yaml
    │       └── chain-breakthrough.yaml
    │
    ├── agent/                            # Agent 运行时
    │   ├── core/
    │   │   ├── prompt_loader.py          # YAML 提示词加载器
    │   │   ├── skill_loader.py           # SKILL.md 加载器
    │   │   ├── llm_router.py             # 多模型路由
    │   │   └── mcp_client.py             # MCP 工具客户端
    │   ├── skills/                       # Skill 绑定
    │   │   ├── chain_analysis.py
    │   │   ├── research_summary.py
    │   │   ├── hotspot_detection.py
    │   │   ├── financial_health.py
    │   │   └── chain_breakthrough.py
    │   ├── tools/                        # 内部工具实现
    │   │   ├── db_tools.py
    │   │   ├── rag_tools.py
    │   │   ├── calc_tools.py
    │   │   └── chart_tools.py
    │   └── router.py                     # Supervisor 路由
    │
    └── mcp/                              # MCP Server 暴露
        └── server.py
```

### 3.2 YAML 提示词文件规范

每个 YAML 文件包含完整提示词、元数据、输出 Schema 和少样本示例：

```yaml
# backend/app/prompts/agents/chain_analyst.yaml
id: chain_analyst
name: 产业链分析专家
version: 1.0.0
model: openai/gpt-4o
description: 对指定行业进行上下游产业链深度分析的专家 Agent

system_prompt: |
  你是一个专业的产业链分析专家。你的任务是：
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

user_prompt_template: |
  ## 目标行业
  {industry}

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

output_schema:
  nodes:
    - name: str
      type: str  # upstream/midstream/downstream
      companies:
        - code: str
          name: str
      avg_gross_margin: float
      bargaining_power: float
  edges:
    - source: str
      target: str
      relation: str
      strength: int
  summary: str
  opportunities: [str]
  risks: [str]

examples:
  - input:
      industry: 半导体
    output:
      nodes:
        - name: 硅材料
          type: upstream
          companies:
            - code: "600703"
              name: 三安光电
          avg_gross_margin: 25.3
          bargaining_power: 7.5
      edges:
        - source: 硅材料
          target: 晶圆制造
          relation: 原材料供应
          strength: 85
      summary: 半导体产业链呈现...
      opportunities:
        - 国产替代加速
      risks:
        - 上游设备受限
```

### 3.3 Skill 提示词文件

```yaml
# backend/app/prompts/skills/industry-chain-analysis.yaml
id: industry-chain-analysis
name: 产业链分析
version: 1.0.0
model: openai/gpt-4o
description: 对指定行业进行上下游产业链分析，输出产业链图谱和分析报告

triggers:
  - 用户要求分析某行业产业链
  - 用户询问某行业上下游关系
  - 用户要求对比产业链不同环节

workflow:
  - 调用 query_industry_companies 获取行业内上市公司
  - 调用 query_financial_data 获取近三期财务数据
  - 调用 search_news 获取近期行业新闻/公告
  - 调用 search_vector_kb 检索产业链相关研报片段
  - 综合分析并生成产业链图谱

system_prompt: |
  你是一个专业的产业链分析专家。
  请严格按照以下步骤分析指定行业，并调用相关工具获取数据。
  最终输出必须符合给定的 JSON Schema。

user_prompt_template: |
  请分析 {industry} 行业的产业链上下游关系，重点关注 {focus}。

output_schema:
  nodes: [...]
  edges: [...]
  summary: str
  opportunities: [str]
  risks: [str]

available_tools:
  - query_industry_companies
  - query_financial_data
  - search_news
  - search_vector_kb
  - calculate_ratio
```

### 3.4 提示词加载器

```python
# backend/app/agent/core/prompt_loader.py
import yaml
from pathlib import Path
from pydantic import BaseModel, Field


class PromptConfig(BaseModel):
    id: str
    name: str
    version: str
    model: str | None = None
    description: str = ""
    system_prompt: str
    user_prompt_template: str = ""
    output_schema: dict = Field(default_factory=dict)
    examples: list[dict] = Field(default_factory=list)
    # Agent 特有
    triggers: list[str] = Field(default_factory=list)
    workflow: list[str] = Field(default_factory=list)
    available_tools: list[str] = Field(default_factory=list)


class PromptLoader:
    def __init__(self, prompts_dir: Path):
        self.prompts_dir = prompts_dir
        self._cache: dict[str, PromptConfig] = {}

    def load(self, scope: str, prompt_id: str) -> PromptConfig:
        key = f"{scope}/{prompt_id}"
        if key in self._cache:
            return self._cache[key]

        path = self.prompts_dir / scope / f"{prompt_id}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Prompt not found: {path}")

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        config = PromptConfig(**data)
        self._cache[key] = config
        return config

    def reload(self, scope: str, prompt_id: str):
        key = f"{scope}/{prompt_id}"
        self._cache.pop(key, None)
        return self.load(scope, prompt_id)
```

### 3.5 渲染提示词

```python
# backend/app/agent/core/prompt_renderer.py
from string import Formatter


class PromptRenderer:
    @staticmethod
    def render(template: str, **kwargs) -> str:
        return template.format(**kwargs)

    @staticmethod
    def get_variables(template: str) -> set[str]:
        return {
            field_name
            for _, field_name, _, _ in Formatter().parse(template)
            if field_name
        }
```

## 4. Skill 体系设计

### 4.1 Skill 与 Prompt 的关系

| 文件 | 用途 |
|------|------|
| `skills/<skill-id>/SKILL.md` | 业务描述：做什么、触发条件、分析流程、输入输出说明（给产品和开发者看） |
| `backend/app/prompts/skills/<skill-id>.yaml` | 执行提示词：system prompt、user prompt 模板、输出 schema、示例（给 LLM 看） |

### 4.2 Skill 目录

```
skills/                                 # 业务 Skill 描述（Markdown）
├── industry-chain-analysis/
│   ├── SKILL.md
│   └── schema.json
├── research-summary/
│   ├── SKILL.md
│   └── schema.json
├── hotspot-detection/
│   ├── SKILL.md
│   └── schema.json
├── financial-health-check/
│   ├── SKILL.md
│   └── schema.json
└── chain-breakthrough/
    ├── SKILL.md
    └── schema.json
```

### 4.3 Skill 加载器

```python
# backend/app/agent/core/skill_loader.py
import json
from pathlib import Path
from pydantic import BaseModel, Field


class SkillMeta(BaseModel):
    id: str
    name: str
    version: str
    model: str | None = None
    timeout: int = 300


class SkillDefinition(BaseModel):
    meta: SkillMeta
    description: str
    triggers: list[str]
    input_schema: dict
    output_schema: dict
    workflow: list[str]
    available_tools: list[str]
    examples: list[dict] = Field(default_factory=list)


class SkillLoader:
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self._skills: dict[str, SkillDefinition] = {}

    def load(self, skill_id: str) -> SkillDefinition:
        if skill_id in self._skills:
            return self._skills[skill_id]

        skill_path = self.skills_dir / skill_id / "SKILL.md"
        schema_path = self.skills_dir / skill_id / "schema.json"

        meta, sections = self._parse_markdown(skill_path.read_text())
        schema = json.loads(schema_path.read_text()) if schema_path.exists() else {}

        skill = SkillDefinition(
            meta=SkillMeta(**meta),
            description=sections.get("描述", ""),
            triggers=self._extract_list(sections.get("触发条件", "")),
            input_schema=schema.get("input", {}),
            output_schema=schema.get("output", {}),
            workflow=sections.get("分析流程", "").split("\n"),
            available_tools=self._extract_tools(sections.get("可用工具", "")),
            examples=self._extract_examples(sections.get("示例", "")),
        )
        self._skills[skill_id] = skill
        return skill
```

## 5. LLM 统一抽象层

### 5.1 模型路由

```python
# backend/app/agent/core/llm_router.py
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai import Agent


PROVIDERS = {
    "openai": OpenAIModel,
    "anthropic": AnthropicModel,
}


def build_model(provider: str, model: str, api_key: str, base_url: str | None = None):
    cls = PROVIDERS.get(provider)
    if not cls:
        raise ValueError(f"Unsupported provider: {provider}")
    return cls(model, api_key=api_key, base_url=base_url)


def build_agent(prompt_config: PromptConfig, model_config: dict) -> Agent:
    model = build_model(
        provider=model_config["provider"],
        model=prompt_config.model or model_config["model"],
        api_key=model_config["api_key"],
        base_url=model_config.get("base_url"),
    )
    return Agent(
        model,
        system_prompt=prompt_config.system_prompt,
        result_type=...,  # 根据 output_schema 动态生成 Pydantic 模型
    )
```

### 5.2 用户自定义模型配置

F-USER-03 模型配置直接复用该路由：

```json
{
  "provider": "openai",
  "base_url": "https://api.openai.com/v1",
  "api_key": "sk-***",
  "model": "gpt-4o",
  "temperature": 0.2
}
```

切换 Anthropic：

```json
{
  "provider": "anthropic",
  "api_key": "sk-ant-***",
  "model": "claude-3-5-sonnet-20241022"
}
```

## 6. MCP 工具集成

### 6.1 内部 MCP Server

平台自身作为 MCP Server 暴露数据工具：

```python
# backend/app/mcp/server.py
from mcp.server import Server
from mcp.types import Tool

app = Server("investment-platform")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="query_industry_companies",
            description="查询指定行业的上市公司列表",
            inputSchema={
                "type": "object",
                "properties": {"industry": {"type": "string"}},
                "required": ["industry"]
            }
        ),
        Tool(
            name="search_vector_kb",
            description="在 Milvus 向量知识库中检索研报/财报片段",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "industry": {"type": "string"},
                    "limit": {"type": "integer", "default": 10}
                },
                "required": ["query"]
            }
        ),
    ]
```

### 6.2 Agent 中使用工具

```python
# backend/app/agent/tools/db_tools.py
from pydantic_ai import Agent


async def build_chain_analysis_agent(prompt_loader, model_config, db, milvus, es):
    prompt = prompt_loader.load("skills", "industry-chain-analysis")
    agent = build_agent(prompt, model_config)

    @agent.tool
    async def query_industry_companies(ctx, industry: str) -> list[dict]:
        """查询指定行业的上市公司列表"""
        result = await ctx.deps.db.execute(
            "SELECT code, name FROM stocks WHERE industry = :industry",
            {"industry": industry}
        )
        return [dict(row) for row in result.mappings()]

    @agent.tool
    async def query_financial_data(ctx, codes: list[str]) -> list[dict]:
        """查询公司财务数据"""
        ...

    return agent
```

## 7. Agent 实现示例

### 7.1 产业链分析 Agent

```python
# backend/app/agent/skills/chain_analysis.py
from pydantic import BaseModel
from pydantic_ai import Agent

from app.agent.core.prompt_loader import PromptLoader
from app.agent.core.llm_router import build_agent
from app.agent.tools import db_tools, rag_tools, calc_tools


class ChainNode(BaseModel):
    name: str
    type: str
    companies: list[dict]
    avg_gross_margin: float
    revenue_growth: float
    bargaining_power: float


class ChainAnalysisOutput(BaseModel):
    nodes: list[ChainNode]
    edges: list[dict]
    summary: str
    opportunities: list[str]
    risks: list[str]


async def analyze_industry_chain(
    industry: str,
    prompt_loader: PromptLoader,
    model_config: dict,
    db,
    milvus,
    es,
) -> ChainAnalysisOutput:
    prompt = prompt_loader.load("skills", "industry-chain-analysis")
    agent: Agent[None, ChainAnalysisOutput] = build_agent(prompt, model_config)

    agent.tool(db_tools.query_industry_companies)
    agent.tool(db_tools.query_financial_data)
    agent.tool(rag_tools.search_vector_kb)
    agent.tool(rag_tools.search_news)
    agent.tool(calc_tools.calculate_ratio)

    user_prompt = PromptRenderer.render(
        prompt.user_prompt_template,
        industry=industry,
        focus="all"
    )

    result = await agent.run(
        user_prompt,
        deps={"db": db, "milvus": milvus, "es": es},
    )
    return result.data
```

### 7.2 Supervisor 路由 Agent

```python
# backend/app/agent/router.py
from pydantic_ai import Agent

from app.agent.core.prompt_loader import PromptLoader
from app.agent.core.llm_router import build_model


async def route_skill(query: str, prompt_loader: PromptLoader, model_config: dict) -> str:
    prompt = prompt_loader.load("agents", "supervisor")
    model = build_model(**model_config)
    agent = Agent(model, system_prompt=prompt.system_prompt)

    user_prompt = PromptRenderer.render(
        prompt.user_prompt_template,
        query=query
    )
    result = await agent.run(user_prompt)
    return result.data.strip()
```

对应的 YAML：

```yaml
# backend/app/prompts/agents/supervisor.yaml
id: supervisor
name: Agent 调度器
version: 1.0.0
system_prompt: |
  你是一个投资分析系统的调度 Agent。
  根据用户的查询，判断需要调用哪个 Skill：
  - industry-chain-analysis：产业链分析
  - research-summary：研报摘要
  - hotspot-detection：热点追踪
  - financial-health-check：财务体检
  - chain-breakthrough：产业链突破点

  仅返回 skill id，不要有任何解释。

user_prompt_template: |
  用户请求：{query}

output_schema:
  skill_id: str
```

### 7.3 研报分析 Agent

```python
# backend/app/agent/skills/research_summary.py
from pydantic import BaseModel
from pydantic_ai import Agent


class ResearchSummaryOutput(BaseModel):
    rating_distribution: dict
    target_price_range: dict
    bullish_points: list[str]
    bearish_points: list[str]
    top_reports: list[dict]


async def summarize_research(
    stock_code: str,
    prompt_loader,
    model_config,
    db,
    minio,
    milvus,
) -> ResearchSummaryOutput:
    prompt = prompt_loader.load("skills", "research-summary")
    agent: Agent[None, ResearchSummaryOutput] = build_agent(prompt, model_config)

    agent.tool(...)

    result = await agent.run(
        PromptRenderer.render(prompt.user_prompt_template, stock_code=stock_code),
        deps={"db": db, "minio": minio, "milvus": milvus},
    )
    return result.data
```

## 8. RAG 管道设计

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
         LLM 生成回答
```

## 9. 调用方式

### 9.1 Web API 调用

```python
# backend/app/api/v1/chain.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.skills.chain_analysis import analyze_industry_chain
from app.agent.core.prompt_loader import PromptLoader
from app.core.database import get_db
from app.core.config import settings

router = APIRouter()


@router.post("/analyze/chain")
async def analyze_chain(payload: ChainAnalysisRequest, db: AsyncSession = Depends(get_db)):
    prompt_loader = PromptLoader(settings.PROMPTS_DIR)
    result = await analyze_industry_chain(
        industry=payload.industry,
        prompt_loader=prompt_loader,
        model_config=settings.DEFAULT_MODEL_CONFIG,
        db=db,
        milvus=...,
        es=...,
    )
    return result
```

### 9.2 定时任务调用

```python
# backend/collector/tasks.py
from app.agent.skills.chain_analysis import analyze_industry_chain


async def scheduled_chain_update(industry: str):
    result = await analyze_industry_chain(
        industry=industry,
        ...,
    )
    await save_chain_analysis(result)
```

### 9.3 MCP 外部调用

外部 AI 工具通过 MCP 调用平台能力时，平台内部同样走 PydanticAI Skill Agent：

```json
{
  "name": "analyze_industry_chain",
  "description": "对指定行业进行产业链分析",
  "inputSchema": {
    "type": "object",
    "properties": {"industry": {"type": "string"}},
    "required": ["industry"]
  }
}
```

## 10. 方案对比

### 10.1 与 Codex CLI 对比

| 维度 | Codex CLI | Python Agent SDK + YAML Prompts |
|------|-----------|--------------------------------|
| **提示词位置** | SKILL.md 内 | `prompts/` YAML 文件 |
| **可控性** | 低 | 高 |
| **多 LLM** | 仅 OpenAI | OpenAI / Anthropic / 兼容模型 |
| **嵌入服务** | 需 subprocess | 直接 import |
| **类型安全** | 无 | Pydantic 强校验 |
| **MCP 支持** | 有限 | 原生支持 |

### 10.2 与 LangGraph 对比

| 维度 | LangGraph | Python Agent SDK + YAML Prompts |
|------|-----------|--------------------------------|
| **复杂度** | 高 | 低 |
| **状态恢复** | 强 | 中 |
| **精确控制** | 强 | 中 |
| **学习成本** | 高 | 低 |
| **提示词管理** | 代码中 | YAML 文件 |
| **适用场景** | 复杂多步工作流 | 分析类 Agent |

### 10.3 Skill vs MCP vs Prompt

| 概念 | Skill | MCP | Prompt YAML |
|------|-------|-----|-------------|
| **本质** | 业务分析指令包 | 工具调用协议 | LLM 提示词配置 |
| **维护者** | 产品/分析师 | 后端工程师 | Prompt 工程师/开发者 |
| **复用范围** | 平台内部 Agent | 内部 + 外部 AI 工具 | 平台内部 Agent |
| **关系** | 声明需要什么 | 提供具体能力 | 驱动 Agent 如何思考 |

## 11. 推荐策略

```
                    ┌──────────────────┐
                    │   用户请求         │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  Supervisor       │
                    │  （prompts/agents/supervisor.yaml）
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
    ┌─────────────┐  ┌───────────┐  ┌──────────────┐
    │ 80% 场景     │  │ 15% 场景  │  │ 5% 场景       │
    │ Skill YAML   │  │ Skill +   │  │ 自定义 Agent  │
    │ 直接执行     │  │ 输出校验   │  │ YAML 流程控制 │
    └─────────────┘  └───────────┘  └──────────────┘
```

**执行策略**：
- **新增分析能力**：优先新增 `skills/<skill-id>/SKILL.md` + `backend/app/prompts/skills/<skill-id>.yaml`，不动代码；
- **调整提示词**：直接改 YAML 文件，服务可热加载；
- **数据工具**：通过 MCP Server 暴露，Agent 和外部工具共用；
- **模型切换**：用户配置中切换 `provider`，底层 `llm_router` 自动适配；
- **需要复杂流程控制**：仅在必要时使用 LangGraph，作为补充而非默认方案。

## 12. 后续文档索引

- [00-overview.md](./00-overview.md) — 总体架构与目录结构
- [05-web-frontend.md](./05-web-frontend.md) — Web + 小程序前端架构
- [06-deployment.md](./06-deployment.md) — 腾讯云部署方案
- [07-testing.md](./07-testing.md) — 测试体系设计
