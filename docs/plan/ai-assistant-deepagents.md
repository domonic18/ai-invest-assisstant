# 对话式 AI 助手实现方案（deepagents）

> 状态：Phase 1 已上线（2026-08-25 验收通过）｜ Phase 2 已验收（2026-08-25）｜ Phase 3-4 规划中 ｜ 创建：2026-08-24 ｜ 关联文档：[04-ai-agent.md](../arch/04-ai-agent.md)

## 1. 背景与目标

### 1.1 问题反馈

1. **系统缺少 AI 助手功能**：现有 AI 能力是分散在各页面的"按钮式"单轮调用（AI 复盘、涨停归因、摘要生成等），不是以 AI 智能体为中心的设计——用户无法用自然语言驱动平台能力。
2. **缺少统一交互入口**：前端需要右侧可唤起的 AI 助手面板，提供对话功能与历史会话查看。
3. **缺少 Skill / MCP 调用能力**：与行业最佳实践对齐，智能体应能按用户意图自主调用 Skill 方法论与 MCP 工具完成任务。
4. **框架选型**：采用行业最新的 [deepagents](https://docs.langchain.com/oss/python/deepagents/overview)（LangChain 出品的开源 Agent Harness）实现。
5. **前端与协议选型**：前端组件库采用 [assistant-ui](https://www.assistant-ui.com)（成熟开源对话组件库）；前后端交互采用 [LangChain Agent Protocol](https://langchain-ai.github.io/agent-protocol/)（thread/run 标准协议，官方提供 OpenAPI 规范与 Python Server Stubs）。

### 1.2 目标

- 任意登录页面右下角可唤起 AI 助手，进行多轮对话，智能体自主规划（内置 TodoList）并调用平台数据工具回答投研问题。
- 会话历史持久化，可回看、可继续。
- 智能体按 Agent Skills 标准渐进加载方法论（SKILL.md），按 MCP 标准调用工具。
- 平台自身作为 MCP Server 对外暴露数据工具，供外部 AI 工具（Claude Code / Cursor 等）调用。

交互硬性需求（用户反馈，逐条实现映射见 5.3）：

1. 流式输出（token 级增量渲染）
2. 思考过程可折叠显示
3. 工具调用过程可折叠显示
4. 可中断 AI 输出并直接下达新任务
5. AI 可向用户提问、用户答复后继续（HITL）

### 1.3 非目标（本期不做）

- 不迁移既有 6 个单轮管线（AI 复盘 / 产业链 / 摘要 / 财务体检等）——它们继续走 PydanticAI，后续按需渐进迁移；其中对助手有价值的能力以"工具"形式暴露给助手复用。
- 不做多租户共享会话、团队协作空间。
- 不做语音/多模态输入。

## 2. 现状盘点

| 资产 | 现状 | 复用方式 |
|------|------|----------|
| `app/agent/core/llm_router.py` + `llm_config` 表 | PydanticAI 双协议模型路由；`resolve_default_llm()` 解密默认配置（Kimi 走 Anthropic 协议） | 保留给既有管线；助手运行时读取同一配置构建 LangChain 模型实例 |
| `app/agent/tools/db_tools.py` | 行情 K 线 / 行业公司 / 财务指标 / 新闻检索 / ES 知识库检索 5 类查询函数 | 直接包装为 LangChain `@tool` |
| `app/services/` 30+ 服务 | 行情、资金流、竞价、研报、财报、自选股等读服务 | 挑选高频能力包装为工具 |
| `app/prompts/agents/` + `skills/` YAML + SKILL.md | YAML 执行提示词（单轮管线用）；根目录 `skills/<id>/SKILL.md` 为自定义中文分区格式 | YAML 保留；SKILL.md 升级为标准 Agent Skills frontmatter 格式（兼容 deepagents 渐进披露） |
| `app/api/v1/mcp/server.py` + `agent/core/mcp_client.py` | 均为空壳（返回空工具） | 本方案落地为真实现 |
| `app/agent/runtime/` | 空目录（仅有 `__init__.py`） | 承载 deepagents 助手运行时 |
| 会话持久化 | **无任何会话/消息表** | 新建 `assistant_session`（消息轨迹由 LangGraph checkpoint 承载） |
| 前端 | 无对话组件；Tailwind + Zustand + TanStack Query 模式成熟 | 引入 assistant-ui（shadcn/ui + Tailwind 风格，与现有栈契合）组装助手面板 |

## 3. 总体架构

```
┌─────────────────────────── Web 前端 ───────────────────────────┐
│  Layout 挂载浮动按钮 → AssistantPanel（Drawer，assistant-ui）   │
│  ├─ useLangGraphRuntime（@assistant-ui/react-langgraph）        │
│  │   └─ @langchain/langgraph-sdk client（JWT 注入）             │
│  └─ 会话列表 / 流式对话 / 折叠思考与工具块 / HITL 卡片 / 图表 UI │
└──────────────────────────────┬──────────────────────────────────┘
                Agent Protocol（HTTP + SSE：threads / runs）
┌──────────────────────────────▼──────────────────────────────────┐
│          api/v1/assistant.py（Agent Protocol 端点，薄路由）      │
│   POST /threads  GET /threads/{id}/state  runs/stream  cancel   │
├─────────────────────────────────────────────────────────────────┤
│              services/assistant_service.py（事务边界）           │
│    会话 CRUD、线程元数据、流事件整形透传、页面上下文注入         │
├─────────────────────────────────────────────────────────────────┤
│              agent/runtime/（deepagents 运行时）                 │
│  create_deep_agent(                                            │
│    model      ← llm_config 默认配置 → ChatAnthropic/ChatOpenAI   │
│    tools      ← assistant_tools（LangChain @tool 包装 services） │
│    skills     ← skills/（标准 frontmatter，渐进披露）            │
│    subagents  ← 领域子代理（Phase 2）                            │
│    checkpointer ← AsyncPostgresSaver（thread_id = 线程 ID）      │
│  )                                                             │
├──────────────────────┬──────────────────────────────────────────┤
│  MCP 双向（Phase 3）  │            PostgreSQL / ES / Milvus      │
│  Server: fastmcp     │  assistant_session（会话列表真相源）      │
│   挂载 /api/v1/mcp   │  langgraph checkpoint 表（消息与线程状态）│
│  Client: admin 配置  │                                          │
│   外部 MCP server    │                                          │
└──────────────────────┴──────────────────────────────────────────┘
```

### 3.1 关键决策与理由

| 决策 | 选择 | 理由 |
|------|------|------|
| 框架共存 | deepagents 仅用于对话助手，既有单轮管线保留 PydanticAI | deepagents 定位是"通用智能体 harness"（规划/工具/文件上下文），不适合替换固定输入输出的结构化管线；避免大爆炸重写 |
| 模型来源 | 复用 `llm_config` 默认配置 | 单一真相来源；后台可切换模型；Kimi（Anthropic 协议）继续可用 |
| 会话双存储 | 应用表（会话列表）+ LangGraph checkpointer（消息与 agent 状态） | UI 会话列表需按 `user_id` 归属分页排序，checkpoint 快照不宜做该查询；消息轨迹由 checkpoint 完整承载、经线程 state 端点读取，不再单建 `assistant_message`，避免双写漂移 |
| 交互协议 | LangChain Agent Protocol（threads / runs / store） | thread/run 标准模型，官方有 OpenAPI 规范与 Python Server Stubs 可参考复用；assistant-ui 的 LangGraph 运行时原生消费这套 API 形状，前端零自定义协议代码 |
| 流式传输 | SSE（`stream_mode=["messages","updates","custom"]`） | Agent Protocol 标准 stream 端点；单向流足够、与现有 HTTP 认证中间件兼容；WebSocket 的双向能力本期用不上 |
| 前端组件库 | assistant-ui（`@assistant-ui/react` + `react-langgraph`） | 成熟开源对话组件库：流式渲染、思考/工具折叠、中断、HITL 均有原生原语；shadcn/ui + Tailwind 与现有栈契合 |
| 内部工具绑定 | LangChain `@tool` 直连服务层 | 助手调平台数据不走 MCP loopback，减少网络跳数与故障面；MCP 用于"对外暴露"与"接入外部" |
| Skills 格式 | SKILL.md 加标准 YAML frontmatter（`name`/`description`） | deepagents SkillsMiddleware 启动只读 frontmatter、按需读全文（渐进披露）；与 Anthropic Agent Skills 行业标准对齐 |

## 4. 后端设计

### 4.1 依赖引入

```bash
cd backend
uv add deepagents langchain-anthropic langchain-openai \
  langgraph-checkpoint-postgres langchain-mcp-adapters fastmcp
```

deepagents 会带入 langchain / langgraph 核心；与 pydantic-ai 无冲突，两者独立共存。Agent Protocol 端点用现有 FastAPI 手写薄层即可（端点形状对齐 4.5 的 wire 子集），落地时可评估复用官方 [Python Server Stubs](https://github.com/langchain-ai/agent-protocol)（FastAPI + Pydantic V2 生成）减少模型定义手写量。

### 4.2 运行时组装（`app/agent/runtime/`）

```
agent/runtime/
├── __init__.py
├── assistant_agent.py      # create_deep_agent 组装（单例，懒加载）
├── assistant_tools.py      # LangChain @tool 包装（Phase 1 核心 8 个）
├── assistant_subagents.py  # 领域子代理声明（Phase 2）
└── model_factory.py        # llm_config → ChatAnthropic / ChatOpenAI
```

`model_factory.py`：

```python
def build_langchain_model(cfg: ResolvedLLMConfig) -> BaseChatModel:
    if cfg.provider == "anthropic":
        return ChatAnthropic(
            model=cfg.model_name, api_key=cfg.api_key, base_url=cfg.base_url,
        )
    return ChatOpenAI(
        model=cfg.model_name, api_key=cfg.api_key, base_url=cfg.base_url,
    )
```

`assistant_agent.py` 核心组装（示意）：

```python
async def get_assistant_agent() -> CompiledStateGraph:
    cfg = await resolve_default_llm_session()
    return create_deep_agent(
        model=build_langchain_model(cfg),
        tools=build_assistant_tools(),
        system_prompt=load_assistant_system_prompt(),   # prompts/agents/assistant.yaml
        skills=[str(SKILLS_DIR)],                      # 根目录 skills/，渐进披露
        subagents=build_subagents(),                   # Phase 2 起启用
        checkpointer=await get_checkpointer(),         # AsyncPostgresSaver 单例
        name="invest-assistant",
    )
```

**约定遵循**：助手 system_prompt 不得硬编码，放 `app/prompts/agents/assistant.yaml`，经 `PromptLoader` 加载（与现有规范一致）。

**Kimi 注意事项**：Anthropic 协议端点 + 强制 tool_choice 会与 thinking 冲突（见既有经验）。deepagents 默认使用原生 tool calling；若默认模型为 Kimi，需在模型实例上禁用 thinking（`extra_headers` 或 model kwargs），并在管理后台 `llm_config.extra` 中可配。

### 4.3 工具层（Phase 1 清单）

全部为**只读查询**工具，复用既有 service / db_tools，避免助手直接触碰写路径：

| 工具名 | 数据来源 | 用途 |
|--------|----------|------|
| `get_stock_quote` | market_service / sina_quote | 个股实时/最新行情快照 |
| `get_stock_kline` | db_tools.query_stock_kline | 个股日 K（近 N 日） |
| `query_financial_data` | db_tools.query_financial_data | 毛利率/营收同比/研发占比等财务指标 |
| `search_news` | db_tools.search_news | 新闻/公告/研报标题摘要检索 |
| `search_vector_kb` | db_tools.search_vector_kb | ES 知识库研报全文检索 |
| `get_sector_fund_flow` | sector_fund_flow_service | 板块资金流向排行 |
| `get_market_overview` | market_stats_service + index spot | 指数行情/涨跌家数/成交额概览 |
| `get_auction_summary` | auction_service | 指数集合竞价表现摘要 |

写操作类工具（触发产业链分析、生成 AI 复盘、加入自选股）放入 Phase 3，并配合 HITL 确认（见 4.8）。

### 4.4 会话持久化

新表（命名遵循 `assistant_` 分类前缀规范）：

```sql
CREATE TABLE assistant_session (
    id              UUID PRIMARY KEY,                  -- 兼作 Agent Protocol thread_id
    user_id         BIGINT NOT NULL,
    title           VARCHAR(128),
    last_message_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_assistant_session_user FOREIGN KEY (user_id) REFERENCES "user" (id)
);
CREATE INDEX idx_assistant_session_user ON assistant_session (user_id, last_message_at DESC);
```

- **不再单建 `assistant_message`**：消息轨迹（含工具调用记录）由 LangGraph checkpoint 完整承载，前端经 `GET /threads/{id}/state` 的 `values.messages` 读取，与 assistant-ui 的 `load()` 回调天然对齐；避免业务表与 checkpoint 双写漂移。
- 标题：首轮对话后取用户消息前 20 字符，或由助手按需生成（同步写 thread metadata 与 `assistant_session.title`）。
- LangGraph checkpoint 表由 `AsyncPostgresSaver.setup()` 在应用 lifespan 中创建（幂等），不手写进 Alembic，避免复制内部表结构。
- **必须同步 `docker/database/init-scripts/01-schema.sql`**（历史三次漂移教训）。

### 4.5 API 设计（Agent Protocol，`app/api/v1/assistant.py`）

后端实现 [LangChain Agent Protocol](https://langchain-ai.github.io/agent-protocol/)（v0.1.6）的 thread/run 模型：端点形状对齐官方 OpenAPI 规范，并覆盖 `@langchain/langgraph-sdk` 实际调用的 wire 子集（assistant-ui 经由该 SDK 消费）。Phase 1 需要的端点：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/assistant/threads` | 新建线程（metadata 写入 `user_id`，同步建 `assistant_session`） |
| GET | `/api/v1/assistant/threads/{thread_id}/state` | 线程状态快照：`values.messages` + `tasks[].interrupts`（前端加载历史/恢复 HITL） |
| GET | `/api/v1/assistant/threads/{thread_id}/history` | checkpoint 历史（消息编辑/重新生成定位父节点） |
| POST | `/api/v1/assistant/threads/{thread_id}/runs/stream` | **SSE 流式运行**：`streamMode: ["messages","updates","custom"]`；`input`（新输入）或 `command`（HITL resume）二选一 |
| POST | `/api/v1/assistant/runs/{run_id}/cancel` | 取消运行（中断输出，前端随即可开新 run） |
| DELETE | `/api/v1/assistant/threads/{thread_id}` | 删除线程（级联 `assistant_session` + checkpoint，校验归属） |
| GET | `/api/v1/assistant/sessions` | 当前用户会话列表（分页，按 last_message_at 倒序；业务端点，非协议部分） |
| GET | `/api/v1/assistant/skills` | 可用 Skill 列表（frontmatter 摘要） |

约束与实现要点：

- **单线程单活跃 run**（协议规定并发互斥）；用户在运行中发新消息时，前端先 `cancel` 再开新 run。
- `on_disconnect: "cancel"`：用户关闭面板/断网即取消运行，避免孤儿 run 占住线程。
- 认证：全部走现有 JWT 依赖；`langgraph-sdk` client 支持自定义 `apiUrl` 与 `defaultHeaders`，前端统一注入。
- 路由层只做参数校验与响应格式，事务在 service 层（遵循分层规范）。

### 4.6 流式事件（stream mode → 前端渲染映射）

`runs/stream` 返回 `text/event-stream`，采用 Agent Protocol 的三种 stream mode 合并输出，`@assistant-ui/react-langgraph` 已内置消费，无需自定义事件协议：

| stream mode | 后端事件来源（`agent.astream`） | 前端渲染 |
|-------------|--------------------------------|----------|
| `messages` | LLM token 增量（`AIMessageChunk`）、工具调用消息 | 文本增量追加；工具调用进入 ToolUI 折叠块 |
| `updates` | 节点状态更新（含 deepagents TodoList `write_todos`） | 计划步骤清单、子代理任务块 |
| `custom` | `push_ui_message(...)`（Generative UI：追问卡片 / 图表） | `makeAssistantDataUI` 注册的渲染器 |

思考过程（需求 ②）：LangGraph 不天然输出 reasoning token，且 Kimi 在 tool calling 场景需禁用 thinking（既有经验）。方案：模型侧支持时（如 Claude 系）以 `messages` 通道中的 reasoning 内容输出，经 assistant-ui 的 reasoning 原语折叠展示；不支持时降级为"计划步骤"（`updates` 通道）充当可折叠过程展示。

实现：服务层把 `agent.astream(..., stream_mode=["messages","updates","custom"], subgraphs=True)` 的事件整形为协议 SSE 帧透传；run 结束后回写 `assistant_session.last_message_at` 与用量统计（metadata）。

### 4.7 MCP 双向（Phase 4）

**平台作为 MCP Server（对外）**：用 `fastmcp` 实现真正的 MCP 端点，替换空壳 `api/v1/mcp/server.py`：

```python
mcp = FastMCP("invest-platform")

@mcp.tool()
async def get_stock_kline(stock_code: str, limit: int = 30) -> list[dict]: ...

# FastAPI 挂载 streamable-http 端点
app.mount("/api/v1/mcp", mcp.http_app(path="/"))
```

鉴权：MCP 端点走独立 API Key（`Authorization: Bearer <api-key>`，管理员在后台生成），不复用用户 JWT。工具注册复用 4.3 的同一批工具函数，保证"给助手的"与"对外的"能力一致。

**助手作为 MCP Client（接入外部）**：管理后台新增外部 MCP Server 配置表（`mcp_server_config`：name/url/认证方式/启用状态），运行时经 `langchain-mcp-adapters` 的 `MultiServerMCPClient` 拉取工具注入助手：

```python
async with MultiServerMCPClient(configured_servers) as client:
    external_tools = await client.get_tools()
```

由于工具集需在 agent 创建时确定，外部 MCP 工具在会话创建时解析并缓存，配置变更后新会话生效。

### 4.8 Subagents 与 HITL（Phase 2 / 3）

- **领域子代理**（`subagents=` 声明，复用内置 `task` 工具派发）：
  - `market-analyst`：行情/技术面/竞价分析
  - `fundamental-analyst`：财务报表/财报/研报知识库检索与解读
  - `news-scout`：热点/新闻/资金流向情报收集
- **HITL**：Phase 3 引入写操作工具（触发采集任务、生成 AI 复盘、自选股写操作）时，`interrupt_on={"tool": [写工具名列表]}` 或图内 `interrupt()`：run 状态转为 `interrupted`，线程 state 的 `tasks[].interrupts` 携带问题载荷；前端 assistant-ui 检测 interrupts 渲染确认卡片（可用 `push_ui_message` 渲染为结构化选项按钮），用户答复后以 `command: {resume: ...}` 发起恢复 run（见 4.5/4.6）。追问场景（AI 主动向用户提问，需求 ⑤）同样走该机制。

## 5. 前端设计（assistant-ui）

### 5.1 技术选型与目录结构

采用 [assistant-ui](https://www.assistant-ui.com)（shadcn/ui 风格对话组件库）+ 其 LangGraph 运行时直连后端 Agent Protocol 端点：

```bash
cd web
npm i @assistant-ui/react @assistant-ui/react-langgraph @langchain/langgraph-sdk
```

```
web/src/
├── components/assistant/
│   ├── AssistantPanel.tsx       # 右侧 Drawer：会话切换 + ThreadPrimitive 对话流
│   ├── AssistantFab.tsx         # 右下角浮动唤起按钮（挂 Layout）
│   ├── AssistantThread.tsx      # assistant-ui primitives 组装（消息流/Markdown/折叠）
│   ├── RuntimeProvider.tsx      # useLangGraphRuntime 注入
│   └── ui/                      # makeAssistantDataUI / makeAssistantToolUI 渲染器
│                                #   （追问卡片、K 线图表、工具详情）
├── hooks/useLangGraphClient.ts  # langgraph-sdk client（baseUrl → /api/v1/assistant，JWT 注入）
└── stores/assistant.ts          # Zustand：panel 开合、当前会话 id
```

运行时接入核心样板（`useLangGraphRuntime` 的 `stream`/`create`/`load` 三回调与 4.5 端点一一对应）：

```tsx
const runtime = useLangGraphRuntime({
  stream: async function* (messages, { initialize, command }) {
    const { externalId } = await initialize();
    const stream = await client.runs.stream(externalId, "invest-assistant", {
      input: messages.length ? { messages } : null,
      command,                                    // HITL resume：LangGraphCommand
      streamMode: ["messages", "updates", "custom"],
    });
    for await (const chunk of stream) yield appendLangChainChunk(chunk);
  },
  create: async () => {
    const { thread_id } = await client.threads.create();
    return { externalId: thread_id };
  },
  load: async (externalId) => {
    const state = await client.threads.getState(externalId);
    return {
      messages: state.values.messages,            // 历史消息（checkpoint 真相源）
      interrupts: state.tasks[0]?.interrupts,     // 未完成的 HITL 提问
    };
  },
});
```

### 5.2 交互要点

- `Layout.tsx` 挂 `<AssistantFab />`，点击展开 Drawer（宽 ~400px，移动端全屏）；ESC/遮罩关闭，运行中关闭即 `cancel`（`on_disconnect: cancel`）。
- 思考过程、工具调用过程用 assistant-ui 的 reasoning / ToolUI 原语（自带折叠态），`useLangGraphMessageMetadata` 补充工具耗时等元信息；不手写折叠组件。
- Generative UI：后端 `push_ui_message("chart", {...})` → 前端 `makeAssistantDataUI({ name: "chart", render })`，在对话流内直接渲染 ECharts 行情图表。
- 发送时携带 `page_context`（当前路由、正在查看的股票/板块）：经 run `metadata` 或注入首条用户消息，实现"页面感知"。
- 历史会话：Drawer 内会话列表（业务端点 `GET /sessions`，TanStack Query）；切换后 `load()` 从线程 state 恢复消息与未完成 interrupts，可继续对话。
- 消息编辑/重新生成：`getCheckpointId` 回调配合 `GET /threads/{id}/history` 定位父 checkpoint。
- 中断：Composer 停止按钮 → `POST /runs/{run_id}/cancel`；用户直接输入新任务时先 cancel 再开新 run（单线程单活跃 run）。

### 5.3 用户交互需求 → 实现映射

| # | 需求 | 实现 |
|---|------|------|
| ① | 流式输出 | run `streamMode: "messages"` → SSE token 增量 → assistant-ui MessagePrimitive 增量渲染 |
| ② | 思考过程可折叠 | 模型 reasoning 内容（`messages` 通道）或 deepagents TodoList（`updates` 通道）→ reasoning / 计划折叠组件 |
| ③ | 工具调用可折叠 | `messages` 通道工具调用消息 + `makeAssistantToolUI`（参数/结果/状态折叠展示） |
| ④ | 中断输出并给新任务 | `POST /runs/{run_id}/cancel` + `on_disconnect: cancel`；同线程立即可开新 run |
| ⑤ | AI 提问/用户答复（HITL） | 图内 `interrupt()` / `interrupt_on` → run `interrupted`、state `tasks[].interrupts` → 确认卡片 → `command {resume}` 恢复 |

## 6. 安全与权限

- 所有 assistant 端点要求登录（复用现有 JWT 依赖），会话操作校验 `user_id` 归属。
- 工具只读优先；工具返回数据前由包装层裁剪行数（防上下文爆炸），敏感字段（成本、密钥）不出现在工具输出。
- MCP 对外端点独立 API Key + 速率限制；工具清单白名单管理（admin 可控）。
- 日志：structlog 记录会话/消息事件（禁止记录完整对话内容与密钥，遵循现有日志规范）。
- CORS 沿用生产域名白名单，不放开。

## 7. 实施计划

### Phase 1：基础对话闭环（约 2 周）

1. 依赖引入 + `model_factory` + `assistant_agent` 组装（无 subagents/skills 先行）
2. `assistant_tools` 8 个只读工具
3. `assistant_session` 表 + Alembic 迁移 + **init-scripts 同步**
4. `assistant_service` + Agent Protocol 端点（threads / state / runs.stream / cancel）+ lifespan 中 checkpointer.setup()
5. 前端 assistant-ui 接入（runtime 三回调）+ AssistantFab / AssistantPanel / 会话列表
6. `prompts/agents/assistant.yaml` 系统提示词
7. 单测：runtime 组装、工具包装、协议 stream 事件整形、service 会话 CRUD（mock 模型）

**验收**：登录后任意页面唤起助手，问"平安银行最近走势如何"，助手调用 kline 工具返回分析；会话历史可回看可继续。

### Phase 2：Skills + Subagents + 页面上下文（约 2 周）

1. ✅ `skills/*/SKILL.md` 加标准 frontmatter（`name`/`description`，正文保留方法论），`skills=` 接入渐进披露
2. ✅ 三个领域子代理 + `task` 派发调优；开 `subgraphs=True` 验证子代理事件透传与事件量影响
3. ✅ 前端渲染 TodoList 计划：解析 `updates` 通道中的 `write_todos` 状态更新，经 Zustand 驱动 `AssistantPanel` 顶部计划条
4. ✅ `page_context` 注入（前端 stream 回调携带当前路由/标的，后端注入用户消息）——从原 Phase 4 提前
5. ✅ `GET /assistant/skills` 端点补全（frontmatter 标准化后自动完整）

**验收**：问"帮我做一次半导体产业链体检"，助手按 SKILL.md 方法论规划步骤、派发子代理、产出结构化分析。

**实际状态**：✅ 已完成（2026-08-25）：5 个 SKILL.md frontmatter 标准化；三个子代理（market-analyst / fundamental-analyst / news-scout）+ subgraphs 事件透传；`TodoListMiddleware` 显式注入使 `write_todos` 在多步任务中可用；前端 `TodoListBar` 实时渲染计划步骤；`page_context` 前后端贯通；Docker 镜像已包含 `/skills/` 目录并配置 `CompositeBackend` 只读挂载。

### Phase 3：写操作 + HITL 确认流（约 1 周，通道 Phase 1 已就绪）

`Interrupt` 序列化、state `tasks[].interrupts`、`command resume` 透传已在 Phase 1 实现并测试，本阶段补齐业务与 UI：

1. 写类工具（触发产业链分析/AI 复盘、自选股管理、触发采集任务）+ `interrupt_on` 配置
2. 前端 HITL 确认卡片（检测 interrupts 渲染、`config.command` resume 发送）
3. 消息用量统计与会话管理（重命名/归档）

**验收**：让助手"把 XX 加入自选股"→ 弹确认卡片 → 确认后真实写入并回报结果。

### Phase 4：MCP 双向（约 2 周）

1. fastmcp 替换空壳 server，挂载 `/api/v1/mcp`（streamable-http + API Key 鉴权）
2. `mcp_server_config` 表 + admin CRUD + 外部 MCP 工具注入助手
3. 用 Claude Code / MCP Inspector 做外部连通性验收

**验收**：外部 MCP 客户端可列出并调用平台 ≥ 5 个数据工具；助手可调用 admin 配置的外部 MCP server 工具。

### 生产上线（Phase 3 完成后统一评估）

暂不上线（2026-08-25 决策：待功能完善后发布）。上线清单：CI 构建推送 TCR → 服务器拉镜像重启 web → 执行 `20260825_assistant_session.sql` → prod compose 核对 `SECRET_KEY`/`CREDENTIAL_ENCRYPTION_KEY` → **Caddy SSE 验证**（确认 `/api/v1/assistant/` 流式路径无缓冲，`X-Accel-Buffering` 对 Caddy 无效，需 `flush_interval -1` 同类配置）。

## 8. 测试与质量

- `tests/unit/agent/`：模型工厂（anthropic/openai 分支）、工具包装（mock session）、stream 事件整形（astream 事件 → 协议 SSE 帧）、prompt 加载
- `tests/unit/services/test_assistant_service.py`：会话 CRUD、归属校验、线程创建联动（mock agent）
- `tests/api/test_assistant.py`（api marker）：threads / runs.stream / cancel 协议端点，FakeAgent 替身
- 前端：`stores/assistant.test.ts`、useLangGraphClient 封装单测
- 完成后跑 `uv run mypy app/ && uv run ruff check . && uv run pytest -m unit`

## 9. 风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| Kimi Anthropic 协议端点与 deepagents 原生 tool calling 兼容性未知 | 助手无法工作 | Phase 1 首日即做模型连通性 spike（tool call 往返）；不行则后台切 OpenAI 兼容端点或换模型 |
| deepagents/langchain 版本迭代快（v0.6→v0.7 middleware API 已变） | 升级破坏 | 锁定次版本；封装 `assistant_agent.py` 单点接触框架 API |
| assistant-ui / Agent Protocol 迭代快（协议 v0.1.x） | 前后端接口漂移 | 前端经 `useLangGraphRuntime` 单点接触运行时 API；后端端点形状以 `@langchain/langgraph-sdk` 实际 wire 子集为准并锁定版本 |
| SSE 长连接与生产 Caddy/SCF 超时 | 流被截断 | Caddy 无默认超时问题，但需关闭缓冲（`flush_interval -1` 已有先例）；SCF 300s 上限内流式心跳 |
| 助手工具返回过大数据撑爆上下文 | 成本/延迟 | 工具层统一裁剪（行数/字符上限），summarization 由 deepagents 内置中间件兜底 |
| checkpoint 表与业务表混用迁移体系 | 漂移 | checkpoint 表仅由 `setup()` 管理；业务表走 Alembic + init-scripts 双同步 |

## 10. 文档更新清单

- [x] `docs/plan/ai-assistant-deepagents.md`（本文档）
- [x] `docs/arch/04-ai-agent.md` — 增补 deepagents 助手层架构章节
- [x] `docs/plan/development-plan.md` — 追加阶段 7、里程碑与优先事项
