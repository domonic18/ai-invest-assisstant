# AI Agent 体系设计

## 1. Agent 体系总览

### 1.1 核心设计目标

- **配置驱动**：Agent 角色、Skill 方法论、系统提示词全部通过 `backend/app/prompts/` 下的 YAML 文件定义，不在代码中硬编码。
- **Skill 与代码解耦**：新增分析能力只需新增 YAML 提示词文件 + `skills/<id>/SKILL.md`，无需改动核心 Agent 代码。
- **多 LLM 协议**：通过统一抽象层同时支持 OpenAI / Anthropic 协议（兼容端点如 Kimi `api.kimi.com/coding` 走 Anthropic 协议）。
- **工具标准化**：内部数据工具统一通过 MCP 协议暴露，既可被 Agent 调用，也可被外部 AI 工具调用。
- **类型安全**：输出结果使用 Pydantic 模型校验，确保 API 返回结构化数据。
- **结构化输出缓存**：相同输入命中 `ai_analysis_result` / `file_metadata.summary` 缓存，避免重复 LLM 调用。

### 1.2 架构全景

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AI Agent 编排层                                   │
│              （PydanticAI + YAML Prompts + MCP）                         │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │         对话式 AI 助手（agent/runtime，deepagents，Phase 1 已上线）  │   │
│  │   右侧面板多轮对话 / Skill 渐进披露 / MCP 工具调用 / 会话历史       │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                YAML 声明式 Skill（prompts/skills/）                │   │
│  │   market-daily-review / limit-up-review / industry-chain-analysis │   │
│  │   research-report-summary / financial-report-summary              │   │
│  │   financial-health-check / hotspot-detection / chain-breakthrough │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │             服务层封装（app/services/）                            │   │
│  │   market_review_service / chain_service / research_service        │   │
│  │   financial_report_service / limit_up_ai_service                  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │             共享能力层（agent/core + agent/tools）                 │   │
│  │   prompt_loader / skill_loader / llm_router / mcp_client          │   │
│  │   db_tools（数据库工具）                                          │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.3 技术选型

| 层次 | 技术 | 说明 |
|------|------|------|
| **Agent SDK** | PydanticAI | Python 原生，类型安全，支持 OpenAI / Anthropic / 兼容端点（单轮管线） |
| **Agent Harness** | deepagents（LangChain/LangGraph） | 对话式 AI 助手运行时：内置规划（TodoList）、Skill 渐进披露、MCP 工具、文件上下文（规划中，见第 10 节） |
| **提示词管理** | YAML 文件 | `backend/app/prompts/` 统一管理 |
| **Skill 业务描述** | `skills/<id>/SKILL.md` | 业务描述用 Markdown，提示词用 YAML |
| **工具协议** | MCP | 内部 / 外部工具统一标准 |
| **模型路由** | `llm_router.build_model` / `build_agent` | OpenAI / Anthropic / 兼容模型 |
| **输出校验** | Pydantic | 结构化输出、API 契约 |

## 2. 当前已实现的 AI 能力

| 能力 | 入口 | 提示词 | 备注 |
|------|------|--------|------|
| 产业链分析（版本化） | `POST /api/v1/chain/analyze` | `skills/industry-chain-analysis.yaml` + `skills/industry-chain-analysis/SKILL.md` | 基于**经营范围自下而上推导环节**，结果以版本形式持久化，支持版本对比 / 详情 / 最新版查询 |
| 每日 AI 大盘综述 | `POST/PUT/GET /api/v1/market/ai-review` | `skills/market-daily-review.yaml` | **YAML 声明式分区**（overview / technical_analysis / capital_analysis / emotion_analysis / risk_advice），section 级编辑时只重生成被改动分区 |
| 涨停 AI 归因 | `POST /api/v1/market/limit-up/ai-review` | `skills/limit-up-review.yaml` | 按行业分组 + 一字 / T 字板形态推导；AI 归因结果按 `input_hash` 缓存 |
| 研报 AI 摘要 | `POST /api/v1/research/{id}/summarize` | `skills/research-report-summary.yaml` | PDF 下载用 `curl_cffi` 绕 WAF；摘要缓存到 `file_metadata.summary` |
| 财报 AI 摘要 | `POST /api/v1/financial-reports/{id}/summarize` | `skills/financial-report-summary.yaml` | 触发采集后异步生成摘要，回写 `file_metadata.summary` |
| 财务体检 | `GET /api/v1/financial/{code}` | `skills/financial-health-check.yaml` | 个股详情 Tab，含近 8 期财务健康度历史趋势 |

> `hotspot-detection`、`chain-breakthrough` 提示词已就位，业务接口随页面迭代补齐。

## 3. 提示词与配置管理

### 3.1 目录结构

```
backend/
└── app/
    ├── prompts/                          # 提示词与 Agent 配置（YAML）
    │   ├── agents/                       # Agent 角色定义
    │   │   ├── supervisor.yaml
    │   │   ├── chain_analyst.yaml
    │   │   ├── research_analyst.yaml
    │   │   ├── hotspot_analyst.yaml
    │   │   └── financial_analyst.yaml
    │   └── skills/                       # Skill 提示词
    │       ├── industry-chain-analysis.yaml
    │       ├── market-daily-review.yaml
    │       ├── limit-up-review.yaml
    │       ├── research-report-summary.yaml
    │       ├── financial-report-summary.yaml
    │       ├── financial-health-check.yaml
    │       ├── hotspot-detection.yaml
    │       └── chain-breakthrough.yaml
    │
    ├── agent/                            # Agent 运行时
    │   ├── core/
    │   │   ├── prompt_loader.py          # YAML 提示词加载器（带缓存与 reload）
    │   │   ├── prompt_renderer.py        # 模板变量渲染
    │   │   ├── skill_loader.py           # SKILL.md 加载器
    │   │   ├── llm_router.py             # OpenAI / Anthropic 双协议路由
    │   │   └── mcp_client.py             # MCP 工具客户端
    │   ├── skills/                       # Skill 运行时绑定
    │   │   └── industry_chain_analysis.py
    │   ├── tools/                        # 内部工具实现
    │   │   └── db_tools.py
    │   └── router.py                     # Supervisor 路由
    │
    └── api/v1/mcp/server.py              # MCP Server 暴露
```

### 3.2 YAML 提示词文件规范

每个 YAML 文件包含完整提示词、元数据、输出 Schema 和少样本示例：

```yaml
id: chain_analyst
name: 产业链分析专家
version: 1.0.0
model: openai/gpt-4o
description: 对指定行业进行上下游产业链深度分析的专家 Agent

system_prompt: |
  你是一个专业的产业链分析专家。你的任务是：
  1. 分析指定行业的产业链上下游关系
  2. 识别各环节的核心上市公司
  ...

user_prompt_template: |
  ## 目标行业
  {industry}

  ## 检索到的上下文
  {context}

output_schema:
  nodes: [...]
  edges: [...]
  summary: str

examples:
  - input: { industry: 半导体 }
    output: { ... }
```

### 3.3 声明式分区（market-daily-review）

`market-daily-review.yaml` 引入了**分区声明**机制：新增分析维度只需在 `sections` 数组追加一条，service 层根据声明决定哪些分区需要重生成、哪些可直接复用底稿。

```yaml
sections:
  - key: overview
    title: AI 大盘综述
    requirements: |
      固定按两段小标题撰写：指数情况 / 量能情况 ...
  - key: technical_analysis
    title: 技术面分析
    requirements: |
      逐标的（沪指/创业板/科创50/沪深300ETF/富时A50）分析日线与周线形态 ...
  - key: capital_analysis
    title: 资金面分析
    requirements: |
      板块资金轮动方向；流入金额标正号、流出金额标负号 ...
  - key: emotion_analysis
    title: 情绪与连板分析
  - key: risk_advice
    title: 风险提示与策略建议
```

`market_review_service.generate_market_review` 按 `sections` 渲染 `section_instructions`，
- 用户编辑过某分区 → 只重生成该分区
- 输入未变（`input_hash` 命中） → 直接返回缓存
- 共享底稿（`market_review_base`）+ 用户覆盖（`user_market_review`）多租户存储

### 3.4 提示词加载器

```python
# backend/app/agent/core/prompt_loader.py
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
    sections: list[PromptSection] = Field(default_factory=list)   # 声明式分区


class PromptLoader:
    def load(self, scope: str, prompt_id: str) -> PromptConfig: ...
    def reload(self, scope: str, prompt_id: str) -> PromptConfig: ...   # 热加载
```

## 4. Skill 体系设计

### 4.1 Skill 与 Prompt 的关系

| 文件 | 用途 |
|------|------|
| `skills/<skill-id>/SKILL.md` | 业务描述：做什么、触发条件、分析流程、输入输出说明（给产品和开发者看） |
| `backend/app/prompts/skills/<skill-id>.yaml` | 执行提示词：system prompt、user prompt 模板、输出 schema、示例（给 LLM 看） |

### 4.2 当前 Skill 目录

```
skills/
├── industry-chain-analysis/        # 已完整实现：服务、API、版本化持久化、单测
│   └── SKILL.md
├── research-summary/
├── financial-health-check/
├── hotspot-detection/
└── chain-breakthrough/
```

### 4.3 产业链 Skill 工具链

`industry-chain-analysis` Skill 是目前唯一端到端跑通的 Agent 能力：

- `agent/skills/industry_chain_analysis.py` — Agent 装配（注入 db_tools）
- `services/chain_service.py` — `analyze_and_persist` / `list_versions` / `get_version_detail` / `get_latest_detail` / `compare_versions`
- `api/v1/chain.py` — 5 个版本管理端点
- 数据落库到 `industry_chain_version` / `industry_chain_node` / `industry_chain_edge` / `industry_chain_company_mapping`
- 推导方式：基于**经营范围**自下而上推导环节（不再要求行业预设）
- 测试：`backend/tests/unit/services/test_chain_service.py` 覆盖 service / tools / API

## 5. LLM 统一抽象层

### 5.1 双协议路由

`agent/core/llm_router.py` 同时支持 OpenAI / Anthropic 协议：

```python
PROVIDERS = {
    "openai":    OpenAIModel,    # OpenAI / DeepSeek / Kimi Moonshot / 自部署 vLLM
    "anthropic": AnthropicModel, # Anthropic / Kimi Coding（api.kimi.com/coding）
}

def build_model(provider: str, model: str, api_key: str, base_url: str | None = None): ...
def build_agent(prompt_config: PromptConfig, model_config: dict) -> Agent: ...
```

> Kimi `api.kimi.com/coding` 走 Anthropic 协议，`provider` 必须为 `anthropic`；结构化输出场景需禁用 thinking。

### 5.2 用户级模型配置

LLM 配置由后台管理（`/api/v1/admin/llm-configs`）维护，API key 用 `app/utils/crypto.py` 加密入库：

```json
{
  "provider": "anthropic",
  "base_url": "https://api.kimi.com/coding",
  "api_key": "<encrypted>",
  "model": "kimi-k2",
  "temperature": 0.2
}
```

## 6. MCP 工具集成

### 6.1 内部 MCP Server

平台自身作为 MCP Server 暴露数据工具（`api/v1/mcp/server.py`）：

```python
@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name="query_industry_companies", ...),
        Tool(name="search_vector_kb", ...),
        ...
    ]
```

### 6.2 Agent 中使用工具

```python
async def build_chain_analysis_agent(prompt_loader, model_config, db, milvus, es):
    prompt = prompt_loader.load("skills", "industry-chain-analysis")
    agent = build_agent(prompt, model_config)

    @agent.tool
    async def query_industry_companies(ctx, industry: str) -> list[dict]: ...

    @agent.tool
    async def query_financial_data(ctx, codes: list[str]) -> list[dict]: ...

    return agent
```

## 7. RAG 管道设计

```
用户查询
    │
    ▼
┌──────────────────────────────────────┐
│         查询重写 (Query Rewrite)       │
└──────────────┬───────────────────────┘
               │
    ┌──────────┼──────────┐
    ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐
│Milvus  │ │Elastic │ │Postgre │
│向量检索 │ │全文检索 │ │结构化查询│
└───┬────┘ └───┬────┘ └───┬────┘
    └──────────┼──────────┘
               ▼
┌──────────────────────────────────────┐
│         结果融合 (Fusion, RRF)         │
└──────────────┬───────────────────────┘
               ▼
         LLM 生成回答
```

## 8. 调用方式

### 8.1 Web API 调用

```python
# backend/app/api/v1/chain.py
@router.post("/analyze", response_model=ChainAnalyzeResponse)
async def analyze_chain(payload: ChainAnalyzeRequest, db: AsyncSession = Depends(get_db)):
    return await chain_service.analyze_and_persist(db=db, **payload.model_dump())
```

服务层调用 Agent，结果按版本写入 `industry_chain_*` 表，前端从版本接口读取。

### 8.2 定时任务调用

`market-daily-review` 由采集 worker 在盘后调度触发：`market-daily-review` 任务的 `internal` 渠道在
`spiders/market_daily_review.py` 中汇总当日数据后调用 `market_review_service` 生成共享底稿。

### 8.3 MCP 外部调用

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

## 9. 方案对比

### 9.1 与 Codex CLI / LangGraph 对比

| 维度 | Codex CLI | LangGraph | **本方案（Python Agent SDK + YAML Prompts）** |
|------|-----------|-----------|---------------------------------------------|
| 提示词位置 | SKILL.md 内 | 代码中 | `prompts/` YAML 文件 |
| 可控性 | 低 | 强 | 高 |
| 多 LLM | 仅 OpenAI | 多 | OpenAI / Anthropic / 兼容模型 |
| 嵌入服务 | 需 subprocess | 直接 import | 直接 import |
| 类型安全 | 无 | 中 | Pydantic 强校验 |
| 学习成本 | 低 | 高 | 低 |
| 适用场景 | 单机分析 | 复杂多步工作流 | 分析类 Agent + 声明式分区 |

### 9.2 Skill vs MCP vs Prompt

| 概念 | Skill | MCP | Prompt YAML |
|------|-------|-----|-------------|
| **本质** | 业务分析指令包 | 工具调用协议 | LLM 提示词配置 |
| **维护者** | 产品 / 分析师 | 后端工程师 | Prompt 工程师 / 开发者 |
| **复用范围** | 平台内部 Agent | 内部 + 外部 AI 工具 | 平台内部 Agent |
| **关系** | 声明需要什么 | 提供具体能力 | 驱动 Agent 如何思考 |

## 10. 对话式 AI 助手（deepagents，Phase 1 已上线 2026-08-25）

现有 AI 能力是各页面"按钮式"单轮管线；对话式助手以 [deepagents](https://docs.langchain.com/oss/python/deepagents/overview)
为运行时，让用户用自然语言驱动平台能力。完整方案见
[ai-assistant-deepagents.md](../plan/ai-assistant-deepagents.md)。

### 10.1 定位与边界

- **新增不重写**：deepagents 仅承载对话助手（`app/agent/runtime/`）；既有 PydanticAI 单轮管线保持不变，其中有价值的能力（产业链分析、AI 复盘等）以工具形式暴露给助手复用。
- **模型同源**：助手经 `resolve_default_llm()` 读取 `llm_config` 默认配置，转换为 LangChain 模型实例（Anthropic 协议 → `ChatAnthropic`，OpenAI 兼容 → `ChatOpenAI`）。
- **标准协议 + 成熟组件**：前后端交互采用 [LangChain Agent Protocol](https://langchain-ai.github.io/agent-protocol/)（thread/run 模型）；前端采用 [assistant-ui](https://www.assistant-ui.com) 组件库，其 `@assistant-ui/react-langgraph` 运行时经 `@langchain/langgraph-sdk` 直连协议端点。

### 10.2 核心组成

| 组成 | 实现 |
|------|------|
| 运行时组装 | `agent/runtime/assistant_agent.py`：`create_deep_agent(model, tools, system_prompt, skills, subagents, checkpointer)` |
| 工具层 | `agent/runtime/assistant_tools.py`：LangChain `@tool` 包装 `db_tools` 与读服务（行情/K线/财务/新闻/知识库/板块资金/大盘/竞价，Phase 1 共 8 个只读工具） |
| Skill 渐进披露 | 根目录 `skills/*/SKILL.md` 升级为标准 frontmatter 格式（`name`/`description`），启动只加载元数据、按需读全文 |
| Subagents | 领域子代理（market-analyst / fundamental-analyst / news-scout）+ 内置 `task` 派发（Phase 2） |
| MCP 双向 | 平台经 fastmcp 对外暴露数据工具（`/api/v1/mcp`，替换现有空壳）；助手经 `langchain-mcp-adapters` 接入外部 MCP Server（Phase 3） |
| 会话持久化 | `assistant_session` 表（会话列表/归属/标题）+ LangGraph `AsyncPostgresSaver`（消息轨迹与 agent 线程状态，`thread_id` 兼作会话 id） |
| API/协议 | `api/v1/assistant.py` 实现 LangChain Agent Protocol：threads / runs（SSE `streamMode: messages·updates·custom`）/ cancel；业务侧仅保留会话列表与 skills 端点 |
| 前端 | assistant-ui 右侧 Drawer 助手面板（流式渲染、思考/工具折叠、中断、HITL 卡片、Generative UI 图表），任意页面右下角唤起 |

### 10.3 分阶段落地

Phase 1 基础对话闭环（工具调用 + 会话历史）→ Phase 2 Skills 标准化 + 子代理 →
Phase 3 MCP 双向 → Phase 4 写操作 + HITL 确认 + 页面上下文注入。
工期与验收标准详见方案文档第 7 节。

## 11. 后续文档索引

- [00-overview.md](./00-overview.md) — 总体架构与目录结构
- [03-data-storage.md](./03-data-storage.md) — 数据库设计（产业链版本表、AI 复盘多租户表）
- [05-web-frontend.md](./05-web-frontend.md) — 前端如何展示版本化分析结果
- [06-deployment.md](./06-deployment.md) — SCF Web 函数（LLM 接口代理超时 300s）
- [ai-assistant-deepagents.md](../plan/ai-assistant-deepagents.md) — 对话式 AI 助手实现方案（deepagents）
