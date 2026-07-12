# AI Agent 体系设计（Skill + Python Agent SDK 版）

## 1. 核心理念转变

### 1.1 为什么放弃 Codex CLI

原始 Skill 方案建议把分析逻辑写成 Codex Skill，由 Codex CLI 的 Agent 引擎自动执行。该方案存在以下问题：

| 问题 | 说明 |
|------|------|
| **黑盒执行** | Codex CLI 是封装好的命令行工具，无法像 SDK 一样单步调试、查看中间状态、精确控制执行路径 |
| **厂商锁定** | 绑定 OpenAI Codex 生态，无法灵活切换 OpenAI / Anthropic / 自托管模型 |
| **难以嵌入服务** | 通过 `subprocess` 调用 CLI 再解析 stdout，不适合生产级 FastAPI 服务 |
| **缺乏状态管理** | 无法做 checkpoint、人机协同、长任务恢复 |
| **闭源不可控** | 行为随 CLI 版本变化，难以建立稳定的回归测试基线 |

因此，本方案**保留 Skill 作为可复用分析指令包**，但**将执行引擎从 Codex CLI 替换为 Python 原生开源 Agent SDK**。

### 1.2 新方案：Python Agent SDK + Skill + MCP

```
Skill 驱动（旧）              Skill + Python Agent SDK（新）
┌──────────────┐             ┌─────────────────────────────┐
│ SKILL.md     │             │ SKILL.md（分析指令/少样本）  │
└──────┬───────┘             └───────────┬─────────────────┘
       │                                 │
       ▼                                 ▼
┌──────────────┐             ┌─────────────────────────────┐
│ Codex CLI    │             │ PydanticAI / OpenAI Agents  │
│ 黑盒 Agent   │   →   →   → │ SDK（Python 原生）           │
│ 闭源         │             │ · Agent + Tool 循环          │
└──────────────┘             │ · 多 LLM 统一抽象            │
                             │ · MCP 工具调用               │
                             │ · Pydantic 输出校验          │
                             └───────────┬─────────────────┘
                                         │
                                         ▼
                             ┌─────────────────────────────┐
                             │ FastAPI 后端服务             │
                             └─────────────────────────────┘
```

**核心原则**：
- **Skill 仍是分析逻辑的可复用单元**（自然语言描述 + 输入输出 Schema + 示例）
- **Python Agent SDK 提供生产级 Agent 执行引擎**（类型安全、多 LLM、MCP、可观测）
- **MCP 作为工具调用标准**（让平台能力既可被内部 Agent 调用，也可被外部 AI 工具调用）
- **不引入 Node.js**，保持后端技术栈统一为 Python

## 2. 技术选型

### 2.1 主选：PydanticAI

| 维度 | PydanticAI |
|------|-----------|
| **定位** | 由 Pydantic 团队出品的 Python Agent 框架 |
| **类型安全** | 原生基于 Pydantic，输入/输出/工具 Schema 自动校验 |
| **多 LLM** | 官方支持 OpenAI、Anthropic、Gemini、Ollama、Groq 等，统一 `Agent` 接口 |
| **MCP 支持** | 原生 `pydantic-ai-mcp` 扩展，支持 MCP Server 作为工具 |
| **FastAPI 集成** | 与 FastAPI/Pydantic 生态无缝融合 |
| **工具注册** | `@agent.tool` 装饰器，自动生成 JSON Schema |
| **依赖注入** | 支持 `deps` 注入数据库会话、配置、用户上下文 |
| **结果校验** | 支持 `result_type` 限定输出 Pydantic 模型 |

### 2.2 备选：OpenAI Agents SDK

| 维度 | OpenAI Agents SDK |
|------|-------------------|
| **定位** | OpenAI 出品的轻量 Agent SDK |
| **核心概念** | `Agent`、`Tool`、`Handoff`、`Runner`（与 Claude SDK Agent 结构接近） |
| **多 LLM** | 名字带 OpenAI，但支持任意 OpenAI 兼容端点（DeepSeek、通义千问、vLLM 等）；Anthropic 可通过兼容层或适配器接入 |
| **MCP 支持** | 官方支持 MCP Server 集成 |
| **适用场景** | 想要最接近 Claude SDK Agent 体验的轻量运行时 |

### 2.3 选型结论

**本项目首选 PydanticAI**，原因：
1. 项目已基于 FastAPI + Pydantic，PydanticAI 是同一套类型体系的自然延伸；
2. 对 OpenAI 和 Anthropic 都是原生支持，不需要兼容层；
3. 输出 Schema 校验、依赖注入、工具注册更符合后端工程化习惯；
4. 比 LangGraph 轻量，比 OpenAI Agents SDK 类型更安全。

**OpenAI Agents SDK 作为备选**：如果团队更熟悉 Claude SDK Agent 的 `Runner` 心智模型，或者需要某些 PydanticAI 暂不支持的功能时使用。

## 3. Skill 体系设计

### 3.1 Skill 目录结构

Skill 作为项目代码的一部分维护：

```
ai-invest-assisstant/
├── skills/                             # Skill 定义（Markdown + 元数据）
│   ├── industry-chain-analysis/
│   │   ├── SKILL.md                    # 分析指令、流程、输出格式
│   │   └── schema.json                 # 输入/输出 JSON Schema
│   ├── research-summary/
│   │   ├── SKILL.md
│   │   └── schema.json
│   ├── hotspot-detection/
│   │   ├── SKILL.md
│   │   └── schema.json
│   ├── financial-health-check/
│   │   ├── SKILL.md
│   │   └── schema.json
│   └── chain-breakthrough/
│       ├── SKILL.md
│       └── schema.json
│
└── backend/
    └── app/
        └── agent/                      # Agent 实现
            ├── __init__.py
            ├── core/                   # 核心引擎
            │   ├── skill_loader.py     # 加载 SKILL.md 与 schema
            │   ├── llm_router.py       # OpenAI / Anthropic 统一路由
            │   ├── mcp_client.py       # MCP 工具客户端
            │   └── agent_factory.py    # 根据 Skill 生成 Agent
            ├── skills/                 # Skill 与 Agent 的绑定
            │   ├── chain_analysis.py
            │   ├── research_summary.py
            │   ├── hotspot_detection.py
            │   ├── financial_health.py
            │   └── chain_breakthrough.py
            ├── tools/                  # 内部工具（也可通过 MCP 暴露）
            │   ├── db_tools.py
            │   ├── rag_tools.py
            │   ├── calc_tools.py
            │   └── chart_tools.py
            └── router.py               # 顶层路由 Agent
```

### 3.2 Skill 文件规范

每个 `SKILL.md` 包含元数据、分析流程、输入输出 Schema：

```markdown
# Industry Chain Analysis

## 元数据
- id: industry-chain-analysis
- name: 产业链分析
- version: 1.0.0
- model: openai/gpt-4o
- timeout: 300

## 描述
对指定行业进行上下游产业链分析，输出产业链图谱和分析报告。

## 触发条件
- 用户要求分析某行业产业链
- 用户询问某行业上下游关系

## 输入参数
```json
{
  "industry": "半导体",
  "focus": "all",
  "history_days": 90
}
```

## 分析流程
1. 调用 `query_industry_companies` 获取行业内上市公司
2. 调用 `query_financial_data` 获取近三期财务数据
3. 调用 `search_news` 获取近期行业新闻/公告
4. 调用 `search_vector_kb` 检索产业链相关研报片段
5. 综合分析并生成产业链图谱

## 输出格式
```json
{
  "nodes": [...],
  "edges": [...],
  "summary": "...",
  "opportunities": [...],
  "risks": [...]
}
```

## 可用工具
- query_industry_companies
- query_financial_data
- search_news
- search_vector_kb
- calculate_ratio
```

### 3.3 Skill 加载器

```python
# backend/app/agent/core/skill_loader.py
import json
import re
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
    system_prompt: str
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
            system_prompt=self._build_system_prompt(sections),
            examples=self._extract_examples(sections.get("示例", "")),
        )
        self._skills[skill_id] = skill
        return skill
```

## 4. LLM 统一抽象层

### 4.1 模型路由

通过 PydanticAI 的 `Agent` 配置切换 OpenAI / Anthropic：

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


def build_agent(skill: SkillDefinition, model_config: dict) -> Agent:
    model = build_model(
        provider=model_config["provider"],
        model=skill.meta.model or model_config["model"],
        api_key=model_config["api_key"],
        base_url=model_config.get("base_url"),
    )
    return Agent(
        model,
        system_prompt=skill.system_prompt,
        result_type=...,  # 根据 output_schema 动态生成 Pydantic 模型
    )
```

### 4.2 用户自定义模型配置

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

切换 Anthropic 只需改 `provider` 和 `model`：

```json
{
  "provider": "anthropic",
  "api_key": "sk-ant-***",
  "model": "claude-3-5-sonnet-20241022"
}
```

## 5. MCP 工具集成

### 5.1 工具分层

```
┌─────────────────────────────────────────┐
│        PydanticAI Agent                 │
│         （Skill 驱动）                   │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│        MCP Client（工具发现/调用）        │
└─────────────────┬───────────────────────┘
                  │
     ┌────────────┼────────────┐
     ▼            ▼            ▼
┌─────────┐  ┌─────────┐  ┌──────────┐
│ 内部 MCP │  │ 外部 MCP│  │ 本地工具  │
│ Server  │  │ Server  │  │（可选）   │
└─────────┘  └─────────┘  └──────────┘
```

### 5.2 内部 MCP Server

平台自身作为 MCP Server 暴露数据工具，Agent 同时作为 MCP Client 调用：

```python
# backend/app/mcp/server.py
from mcp.server import Server
from mcp.types import Tool, TextContent

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

### 5.3 Agent 中使用工具

```python
# backend/app/agent/tools/db_tools.py
from pydantic_ai import Agent
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.core.skill_loader import SkillLoader
from app.agent.core.llm_router import build_agent
from app.core.database import get_db


async def build_chain_analysis_agent(
    skill_loader: SkillLoader,
    model_config: dict,
    db: AsyncSession,
):
    skill = skill_loader.load("industry-chain-analysis")
    agent = build_agent(skill, model_config)

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

## 6. Agent 运行示例

### 6.1 产业链分析 Agent

```python
# backend/app/agent/skills/chain_analysis.py
from pydantic import BaseModel
from pydantic_ai import Agent

from app.agent.core.skill_loader import SkillLoader
from app.agent.core.llm_router import build_agent
from app.agent.tools import db_tools, rag_tools, calc_tools


class ChainNode(BaseModel):
    name: str
    type: str  # upstream / midstream / downstream
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
    skill_loader: SkillLoader,
    model_config: dict,
    db,
    milvus,
    es,
) -> ChainAnalysisOutput:
    skill = skill_loader.load("industry-chain-analysis")
    agent: Agent[None, ChainAnalysisOutput] = build_agent(skill, model_config)

    # 注册工具
    agent.tool(db_tools.query_industry_companies)
    agent.tool(db_tools.query_financial_data)
    agent.tool(rag_tools.search_vector_kb)
    agent.tool(rag_tools.search_news)
    agent.tool(calc_tools.calculate_ratio)

    result = await agent.run(
        f"请分析 {industry} 行业的产业链上下游关系",
        deps={"db": db, "milvus": milvus, "es": es},
    )
    return result.data
```

### 6.2 顶层路由

```python
# backend/app/agent/router.py
from pydantic_ai import Agent


async def route_skill(query: str, model_config: dict) -> str:
    """根据用户请求匹配 Skill"""
    router = Agent(
        build_model(**model_config),
        system_prompt="""
根据用户请求，选择最合适的 Skill：
- industry-chain-analysis：产业链分析
- research-summary：研报摘要
- hotspot-detection：热点追踪
- financial-health-check：财务体检
- chain-breakthrough：产业链突破点

仅返回 skill id。
""",
    )
    result = await router.run(query)
    return result.data.strip()
```

## 7. 调用方式

### 7.1 Web API 调用

```python
# backend/app/api/v1/chain.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.skills.chain_analysis import analyze_industry_chain
from app.agent.core.skill_loader import SkillLoader
from app.core.database import get_db
from app.core.config import settings

router = APIRouter()


@router.post("/analyze/chain")
async def analyze_chain(payload: ChainAnalysisRequest, db: AsyncSession = Depends(get_db)):
    """产业链分析 API：调用 PydanticAI Skill Agent"""
    skill_loader = SkillLoader(settings.SKILLS_DIR)
    result = await analyze_industry_chain(
        industry=payload.industry,
        skill_loader=skill_loader,
        model_config=settings.DEFAULT_MODEL_CONFIG,
        db=db,
        milvus=...,
        es=...,
    )
    return result
```

### 7.2 定时任务调用

```python
# backend/collector/tasks.py
from app.agent.skills.chain_analysis import analyze_industry_chain


async def scheduled_chain_update(industry: str):
    """每周自动执行产业链分析 Skill"""
    result = await analyze_industry_chain(
        industry=industry,
        ...,
    )
    await save_chain_analysis(result)
```

### 7.3 MCP 外部调用

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

## 8. 方案对比

### 8.1 与 Codex CLI 对比

| 维度 | Codex CLI | PydanticAI / OpenAI Agents SDK |
|------|-----------|-------------------------------|
| **开发方式** | 写 SKILL.md，CLI 黑盒执行 | SKILL.md + Python Agent 编排 |
| **可控性** | 低 | 高，Agent/Tool/State 全可见 |
| **多 LLM** | 仅 OpenAI | OpenAI / Anthropic / 兼容模型 |
| **嵌入服务** | 需 subprocess | 直接 import 调用 |
| **类型安全** | 无 | PydanticAI 强 / OpenAI Agents SDK 中 |
| **MCP 支持** | 有限 | 原生支持 |
| **厂商锁定** | 高 | 低，完全开源 |

### 8.2 与 LangGraph 对比

| 维度 | LangGraph | PydanticAI / OpenAI Agents SDK |
|------|-----------|-------------------------------|
| **复杂度** | 高（图编排） | 低（Agent + Tool 循环） |
| **状态恢复** | 强（checkpoint） | 中（session/依赖注入） |
| **精确控制** | 强（Node/Edge） | 中（工具调用 + 系统提示） |
| **学习成本** | 高 | 低 |
| **适用场景** | 复杂多步工作流 | 分析类 Agent、API 服务 |

### 8.3 Skill vs MCP

| 概念 | Skill | MCP |
|------|-------|-----|
| **本质** | 可复用的分析指令包（做什么） | 工具调用协议（怎么做/怎么调用） |
| **内容** | system prompt、流程、schema、示例 | tool schema、调用入口、返回格式 |
| **复用范围** | 平台内部 Agent | 内部 Agent + 外部 AI 工具 |
| **关系** | Skill 声明需要哪些 MCP 工具 | MCP 提供 Skill 所需的具体能力 |

## 9. 推荐策略

```
                    ┌──────────────────┐
                    │   用户请求         │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  Router Agent     │
                    │  匹配 Skill       │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
    ┌─────────────┐  ┌───────────┐  ┌──────────────┐
    │ 80% 场景     │  │ 15% 场景  │  │ 5% 场景       │
    │ Skill 直接   │  │ Skill +   │  │ 自定义 Agent  │
    │ PydanticAI   │  │ 输出校验   │  │ 流程控制      │
    │ 自动执行     │  │ 节点       │  │               │
    └─────────────┘  └───────────┘  └──────────────┘
```

**执行策略**：
- **分析类任务**：用 `SKILL.md` 描述分析流程，PydanticAI 加载并执行
- **数据查询/计算**：通过 MCP Server 暴露为工具，供 Agent 和外部共同使用
- **需要精确控制的多步推理**：在 PydanticAI 中通过多个 Agent / tool 组合实现，必要时回退到 LangGraph
- **模型选择**：默认 OpenAI，用户可在设置中切换 Anthropic 或其他兼容 OpenAI 协议的模型

大部分新增分析需求只需新增或修改 `skills/<skill-id>/SKILL.md`，无需改动核心 Agent 代码。

## 10. 后续文档索引

- [00-overview.md](./00-overview.md) — 总体架构与目录结构
- [04-ai-agent.md](./04-ai-agent.md) — 原始 LangGraph 代码方案（已并入本方案作为实现参考）
- [05-web-frontend.md](./05-web-frontend.md) — Web + 小程序前端架构
- [06-deployment.md](./06-deployment.md) — 腾讯云部署方案
