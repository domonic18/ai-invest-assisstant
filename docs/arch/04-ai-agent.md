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
│              （deepagents / LangChain + YAML Prompts + MCP）             │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │         对话式 AI 助手（agent/runtime，deepagents 运行时）          │   │
│  │   右侧面板多轮对话 / Skill 渐进披露 / 工具调用 / 会话历史           │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │           Skill 执行器（agent/skills，deepagents 骨架）            │   │
│  │   多步 agent 循环：复盘综述 / 个股每日分析 / 涨停归因 / 产业链     │   │
│  │   单轮结构化（with_structured_output）：研报摘要 / 财报摘要 /      │   │
│  │   截图识别（视觉）                                                 │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │             服务层封装（app/services/）                            │   │
│  │   market_review_service / chain_service / research_service        │   │
│  │   financial_report_service / limit_up_ai_service                  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │             共享能力层（agent/core + agent/tools + runtime）       │   │
│  │   prompt_loader / prompt_renderer / model_factory / structured    │   │
│  │   skill_runtime（执行骨架）/ 内部工具 + page_event / MCP 工具适配  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.3 技术选型

| 层次 | 技术 | 说明 |
|------|------|------|
| **Agent 运行时** | deepagents（LangChain/LangGraph） | 全部 AI 功能统一运行时：多步任务走 agent 循环（LLM 自主调工具），单轮任务走 `with_structured_output` 一次调用（`runtime/structured.py`） |
| **模型工厂** | `runtime/model_factory.build_langchain_model` | OpenAI 兼容端点 → `ChatOpenAI`；Anthropic 协议（含 Kimi coding）→ `ChatAnthropic` |
| **提示词管理** | YAML 文件 | `backend/app/prompts/` 统一管理 |
| **Skill 业务描述** | `skills/<id>/SKILL.md` | 业务描述用 Markdown，提示词用 YAML |
| **工具协议** | MCP | 内部 / 外部工具统一标准 |
| **输出校验** | Pydantic | 结构化输出、API 契约 |

## 2. 当前已实现的 AI 能力

| 能力 | 入口 | 提示词 | 备注 |
|------|------|--------|------|
| 产业链分析（版本化） | 页面按钮 → AI 助手侧边栏；`POST /api/v1/chain/analyze` 与每周 `chain-refresh` 定时任务 | `skills/industry-chain-analysis/prompt.yaml` | 基于**经营范围自下而上推导环节**，结果以版本形式持久化，支持版本对比 / 详情 / 最新版查询 |
| 每日 AI 大盘综述 | 页面/管理后台按钮 → AI 助手侧边栏；`GET/PUT /api/v1/market/ai-review` 读写；每交易日 16:30 定时 | `skills/market-daily-review/prompt.yaml` | **YAML 声明式分区**（overview / technical_analysis / capital_analysis / emotion_analysis / risk_advice），section 级编辑时只重生成被改动分区 |
| 涨停 AI 归因 | 页面按钮 → AI 助手侧边栏；每交易日 16:30 定时 | `skills/limit-up-review/prompt.yaml` | 按题材分组 + 一字 / T 字板形态推导；AI 归因结果按 `input_hash` 缓存 |
| 研报 AI 摘要 | `POST /api/v1/research/{id}/summarize`；助手对话调用 | `skills/research-report-summary/prompt.yaml` | PDF 下载用 `curl_cffi` 绕 WAF；摘要缓存到 `file_metadata.summary` |
| 财报 AI 摘要 | `POST /api/v1/financial-reports/{id}/summarize`；助手对话调用 | `skills/financial-report-summary/prompt.yaml` | 触发采集后异步生成摘要，回写 `file_metadata.summary` |
| 资讯重要度分级 | 资讯中心（电报/重点跟踪）；助手对话调用 | `skills/news-score/prompt.yaml` | 对电报 / 资讯打重要度分并给理由，驱动「重点与跟踪」筛选 |
| 事件故事线建线 | 资讯中心（重点与跟踪）；助手对话调用 | `skills/news-storyline/prompt.yaml` | 从资讯中识别事件并建/续故事线，持续跟踪演进 |
| 热点主题聚类 | 资讯中心（热点主题）；助手对话调用 | `skills/news-topic/prompt.yaml` | 资讯聚类为热点主题榜（主题 / 情绪 / 传导链） |
| 自选股 AI 每日分析 | 个股页按钮 → AI 助手侧边栏；每交易日 16:40 批量（heavy 队列） | `skills/stock-daily-analysis/prompt.yaml` | 三段式输出（盘面解读 / 操作策略 / 止损线），按 `input_hash`（skill+code+日期）缓存；展示于个股详情 Tab 与自选股列表卡片 |
| 自选股截图识别 | `POST /api/v1/users/watchlist/recognize-screenshot` | `skills/watchlist-screenshot-recognition/prompt.yaml` | 视觉模型识别截图中的股票列表，与 `stock_basic` 交叉校验后返回 |

> `hotspot-detection`、`chain-breakthrough`、`financial-health-check` 为 `doc_only` 方法论技能（仅 `skills/*/SKILL.md` 业务描述），实现随页面迭代补齐。

## 3. 提示词与配置管理

### 3.1 目录结构

```
backend/
└── app/
    ├── prompts/                          # Agent 角色提示词（YAML）
    │   └── agents/                       # assistant / page_context / subagent_{fundamental,market,news}
    │
    ├── skills/                           # Skill 注册与提示词加载
    │   ├── registry.py                   # BUILTIN_SKILLS 声明表（id / kind / scenario / skill_md，测试钉死）
    │   ├── prompt.py                     # load_skill_prompt：skills/<id>/prompt.yaml → PromptConfig
    │   └── skill_sync.py                 # 启动时把 builtin skill 同步回填 DB（services/skill/）
    │
    ├── agent/                            # Agent 运行时
    │   ├── core/
    │   │   ├── prompt_loader.py          # Agent 角色 YAML 加载器（带缓存与 reload）
    │   │   └── prompt_renderer.py        # 模板变量渲染
    │   ├── runtime/                      # 对话助手与共享运行时（见第 10 节）
    │   │   ├── assistant_agent.py        # create_deep_agent 组装（内部工具 + MCP 工具，缓存单例 + reset）
    │   │   ├── assistant_subagents.py    # 领域子代理
    │   │   ├── model_factory.py          # llm_config → LangChain 模型
    │   │   ├── structured.py             # 单轮结构化调用（with_structured_output）
    │   │   └── wire.py                   # 消息序列化（Agent Protocol）
    │   ├── skills/                       # Skill 执行器
    │   │   ├── skill_runtime.py          # deepagents 执行骨架（invoke/invoke_sections/invoke_structured）
    │   │   ├── market_review_agent.py / stock_daily_analysis_agent.py
    │   │   ├── limit_up_review_agent.py / industry_chain_analysis.py
    │   │   └── watchlist_screenshot_recognition.py
    │   └── tools/                        # LangChain @tool 内部工具实现
    │       ├── db_tools.py
    │       ├── chain_tools.py / market_tools.py / news_tools.py
    │       ├── report_tools.py / stock_tools.py
    │       ├── page_event.py             # page_event("<domain>.complete") 事件构造（SSE 回写前端）
    │       └── __init__.py               # build_assistant_tools() / build_mcp_tools()
    │
    └── api/v1/mcp/server.py              # MCP Server 暴露
```

skill 提示词不属于 `prompts/`——它是 skill 分发单元的一部分，与 `SKILL.md` 同目录放在根 `skills/<skill-id>/prompt.yaml`，经 `app.skills.prompt.load_skill_prompt` 加载。

### 3.2 YAML 提示词文件规范

每个 YAML 文件包含元数据、system prompt 与 user prompt 模板（分区型 Skill 额外声明 `sections`）：

```yaml
id: industry-chain-analysis
name: 产业链分析
version: 1.0.0
description: 对指定行业进行上下游产业链深度分析

system_prompt: |
  你是一个专业的产业链分析专家。你的任务是：
  1. 分析指定行业的产业链上下游关系
  2. 识别各环节的核心上市公司
  ...

user_prompt_template: |
  ## 目标行业
  {industry}

  ## 关注焦点（可选）
  {focus}
```

### 3.3 声明式分区（market-daily-review）

`skills/market-daily-review/prompt.yaml` 引入了**分区声明**机制：新增分析维度只需在 `sections` 数组追加一条，service 层根据声明决定哪些分区需要重生成、哪些可直接复用底稿。

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
- 共享底稿（复用 `ai_analysis_result`，input_hash 幂等缓存）+ 用户覆盖（`user_market_review`）多租户存储

### 3.4 提示词加载器

```python
# backend/app/agent/core/prompt_loader.py
class PromptConfig(BaseModel):
    id: str
    name: str
    version: str
    description: str = ""
    system_prompt: str
    user_prompt_template: str = ""
    sections: list[PromptSection] = Field(default_factory=list)   # 声明式分区


class PromptLoader:
    def load(self, scope: str, prompt_id: str) -> PromptConfig: ...
    def reload(self, scope: str, prompt_id: str) -> PromptConfig: ...   # 热加载
```

## 4. Skill 体系设计

### 4.1 Skill 与 Prompt 的关系

每个 skill 是 `skills/<skill-id>/` 下的自包含分发单元：

| 文件 | 用途 |
|------|------|
| `skills/<skill-id>/SKILL.md` | 业务描述 + frontmatter（`name`/`description`）：做什么、触发条件、allowed-tools、输出说明；助手渐进披露加载 |
| `skills/<skill-id>/prompt.yaml` | 执行提示词：system prompt、user prompt 模板、输出 schema、示例（给 LLM 看） |

### 4.2 Skill 注册与场景分类

13 个 builtin skill 在 `app/skills/registry.py` 的 `BUILTIN_SKILLS` 声明表登记（id / kind / scenario / skill_md，`tests/unit/skills/test_registry.py` 钉死一致性），启动时 `sync_builtin_skills` 回填 `skill` 表：

- **kind（能力形态）**：`executable`（自动化·定时）/ `prompt_only`（对话调用）/ `doc_only`（方法论）
- **scenario（业务场景，技能广场 Tab 维度）**：`market` 大盘与情绪 / `stock` 个股分析 / `chain` 产业链 / `report` 财报与研报 / `news` 资讯处理；用户自定义技能固定 `custom`。枚举唯一真相源在 `registry.py` 与 `shared/types/skill.ts` 两侧对齐
- 自定义技能经 `POST /api/v1/skills`（配置非代码）创建；`POST /api/v1/skills/analyze` 解析上传的标准 zip 压缩包（magic-byte 校验、zip-slip 防护、secret 扫描、解析 SKILL.md frontmatter）自动预填表单

### 4.3 当前 Skill 目录

```
skills/
├── industry-chain-analysis/        # executable · chain：版本化分析（服务、API、持久化、单测）
├── market-daily-review/            # executable · market：分区生成、版本对比
├── limit-up-review/                # executable · market：涨停归因 + input_hash 缓存
├── stock-daily-analysis/           # executable · stock：自选股盘后批量分析
├── watchlist-screenshot-recognition/  # executable · stock：截图识别（视觉）
├── research-report-summary/        # prompt_only · report：研报摘要
├── financial-report-summary/       # prompt_only · report：财报摘要
├── news-score/                     # prompt_only · news：资讯重要度分级
├── news-storyline/                 # prompt_only · news：事件故事线建线
├── news-topic/                     # prompt_only · news：热点主题聚类
├── financial-health-check/         # doc_only · stock：方法论，实现待补
├── hotspot-detection/              # doc_only · market：方法论，实现待补
└── chain-breakthrough/             # doc_only · chain：方法论，实现待补
```

### 4.4 产业链 Skill 工具链

`industry-chain-analysis` 是最完整的 Skill 能力：

- `agent/skills/industry_chain_analysis.py` — deepagents 执行器（注入取数工具，后置校验剔除幻觉代码）
- `services/chain/chain_service.py` — 版本管理与对比（`list_versions` / `get_version_detail` / `get_latest_detail` / `compare_versions`）
- `services/chain/chain_analysis_service.py` — `analyze_and_persist` / `persist_analysis_result`
- `api/v1/chain.py` — 5 个版本管理端点
- 数据落库到 `industry_chain_analysis_version` / `industry_chain_node` / `industry_chain_edge` / `industry_chain_company_mapping`
- 推导方式：基于**经营范围**自下而上推导环节（不再要求行业预设）
- 测试：`backend/tests/unit/services/test_chain_service.py` 覆盖 service / tools / API

## 5. LLM 统一抽象层

### 5.1 模型工厂

`agent/runtime/model_factory.py` 把后台 LLM 配置统一转换为 LangChain 模型实例：

```python
PROVIDERS = {
    "openai":    ChatOpenAI,     # OpenAI / DeepSeek / Kimi Moonshot / 自部署 vLLM
    "anthropic": ChatAnthropic,  # Anthropic / Kimi Coding（api.kimi.com/coding）
}

def build_langchain_model(cfg: ResolvedLLMConfig) -> BaseChatModel: ...
```

统一注入 `llm_http_read_timeout` 读超时与 `llm_max_retries` 重试次数；助手与单轮结构化调用共用此入口。

> Kimi `api.kimi.com/coding` 走 Anthropic 协议，`provider` 必须为 `anthropic`。

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

平台自身作为 MCP Server 暴露数据工具（`api/v1/mcp/server.py`），内部 Agent 与外部 AI 工具共用同一套工具面。

### 6.2 Agent 中使用内部工具

内部数据工具统一以 LangChain `@tool` 定义于 `agent/tools/`，deepagents 助手与各 Skill 执行器共用：

```python
# agent/tools/chain_tools.py
@tool
def query_industry_companies(industry: str, limit: int = 150) -> dict: ...

# agent/skills/industry_chain_analysis.py
agent = create_deep_agent(
    model=build_langchain_model(cfg),
    tools=[get_industry_companies, get_financial_metrics, search_news],
    system_prompt=prompt_config.system_prompt,
)
result = await skill_runtime.invoke_structured(agent, user_prompt, ChainAnalysisResult)
```

### 6.3 外部 MCP Server 接入助手

外部 MCP 服务经后台管理（`/admin/mcp-servers` → `api/v1/admin/mcp_configs.py` + `services/admin/mcp_config_service.py`）维护配置，启用后工具注入对话助手：

- **配置**：`mcp_server_config` 表（transport_type = `http`(Streamable) / `sse` / `stdio`，url/command+args/env/headers、timeout_seconds、enabled、last_status）；表单支持从 Claude Desktop / Cursor 标准 `mcpServers` JSON 导入预填；保存前可发起连接测试（成功返回工具清单，失败折叠为可读错误，密钥不落日志）
- **注入**：`agent/tools/build_mcp_tools()` 读取 enabled 配置，经 `langchain-mcp-adapters` 的 `MultiServerMCPClient` 逐服务适配为 LangChain 工具；`assistant_agent` 组装时 `tools = [*build_assistant_tools(), *await build_mcp_tools()]`
- **容错**：单服务连接失败只记日志不阻断其余服务；工具名冲突保留先注册者；工具在每次调用时新建会话（不维持长连接）
- **热更**：助手 agent 为缓存单例，配置保存 / 修改后服务层调 `reset_assistant_agent()` 重建即生效

## 7. 知识检索

LLM 上下文供给走三类检索，未引入向量库：

| 检索路径 | 载体 | 场景 |
|----------|------|------|
| 结构化查询 | PostgreSQL（`agent/tools/db_tools`） | 行情/财务/股池/产业链数据注入 prompt |
| 全文检索 | Elasticsearch | 新闻/公告语义关键词召回 |
| 文档直读 | COS（PDF）+ `file_metadata.summary` 缓存摘要 | 研报/财报摘要 Skill |

> 如未来需要文档级语义检索（Embedding + 向量库），再行评估引入，当前规模下结构化 + 全文检索已满足分析类 Skill 的上下文需求。

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

三个 AI 生成任务由采集调度自动触发（internal 渠道，heavy 队列）：

- **每日复盘综述**：交易日 15:05，`spiders/market_daily_review.py` 汇总当日数据后调用 `market_review_service` 生成共享底稿
- **涨停 AI 归因**：交易日 16:30，`spiders/limit_up_ai_review.py` 调用 `limit_up_ai_service.generate_attribution`（依赖 16:00 涨停股池；未就绪由 Celery 10 分钟退避重试 3 次兜底）
- **自选股 AI 每日分析**：交易日盘后，`spiders/watchlist_daily_analysis.py` 仅遍历**开启 AI 复盘开关的分组**（`watchlist_group.ai_review_enabled`）逐只生成三段式分析（盘面解读 / 操作策略 / 止损线），单股串行避免并发限流；未开启分组的标的不消耗 LLM

三者结果均按 `input_hash`（`skill_id` + 业务键：复盘 / 归因为日期，自选股分析为 code+日期）缓存于 `ai_analysis_result`，已生成则 SKIPPED；Redis 分布式锁防止定时任务与手动点击并发双跑 LLM。

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

| 维度 | Codex CLI | LangGraph | **本方案（deepagents + YAML Prompts）** |
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

## 10. 对话式 AI 助手（deepagents）

现有 AI 能力是各页面"按钮式"单轮管线；对话式助手以 [deepagents](https://docs.langchain.com/oss/python/deepagents/overview)
为运行时，让用户用自然语言驱动平台能力。

### 10.1 定位与边界

- **单一运行时**：deepagents（`app/agent/runtime/`）承载全部 AI 功能——对话助手走多轮 agent 循环，各分析 Skill 执行器复用 `skill_runtime` 骨架，单轮任务（摘要/截图识别）走 `structured.run_structured`。
- **模型同源**：助手经 `resolve_default_llm()` 读取 `llm_config` 默认配置，经 `model_factory` 转换为 LangChain 模型实例（Anthropic 协议 → `ChatAnthropic`，OpenAI 兼容 → `ChatOpenAI`）。
- **标准协议 + 成熟组件**：前后端交互采用 [LangChain Agent Protocol](https://langchain-ai.github.io/agent-protocol/)（thread/run 模型）；前端采用 [assistant-ui](https://www.assistant-ui.com) 组件库，其 `@assistant-ui/react-langgraph` 运行时经 `@langchain/langgraph-sdk` 直连协议端点。

### 10.2 核心组成

| 组成 | 实现 |
|------|------|
| 运行时组装 | `agent/runtime/assistant_agent.py`：`create_deep_agent(model, tools, system_prompt, skills, subagents, checkpointer)` |
| 工具层 | `app/agent/tools.build_assistant_tools()`：LangChain `@tool` 包装 `db_tools` 与读服务（行情/K线/财务/新闻/知识库/板块资金/大盘/竞价等只读工具 + 复盘/归因/产业链/个股分析持久化工具 + 财报工具 + 行情补采）；`build_mcp_tools()` 经 `langchain-mcp-adapters` 注入后台已启用的外部 MCP 服务工具（见 6.3） |
| Skill 渐进披露 | 根目录 `skills/*/SKILL.md` 标准 frontmatter 格式（`name`/`description`），启动只加载元数据、按需读全文 |
| MCP 双向 | 平台经 fastmcp 对外暴露数据工具（`/api/v1/mcp`）；助手经 `langchain-mcp-adapters` 接入外部 MCP Server（后台 `/admin/mcp-servers` 维护配置与连接测试，启用即注入） |
| 会话持久化 | `assistant_session` 表（会话列表/归属/标题）+ LangGraph `AsyncPostgresSaver`（消息轨迹与 agent 线程状态，`thread_id` 兼作会话 id） |
| API/协议 | `api/v1/assistant.py` 实现 LangChain Agent Protocol：threads / runs（SSE `streamMode: messages·updates·custom`）/ cancel；业务侧仅保留会话列表与 skills 端点 |
| 前端 | assistant-ui 右侧 Drawer 助手面板（流式渲染、思考/工具折叠、中断、HITL 卡片、Generative UI 图表），任意页面右下角唤起 |

> 后续演进方向（领域子代理派发、写操作 + HITL 确认等）按需规划实施；页面上下文注入（`page_context`）已实现。

## 11. 后续文档索引

- [00-overview.md](./00-overview.md) — 总体架构与目录结构
- [03-data-storage.md](./03-data-storage.md) — 数据库设计（产业链版本表、AI 复盘多租户表）
- [05-web-frontend.md](./05-web-frontend.md) — 前端如何展示版本化分析结果
- [06-deployment.md](./06-deployment.md) — 部署架构（SCF 承载）
