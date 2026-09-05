# AI Invest Assistant - Claude Code AI 上下文文件

## 1. 项目概览

- **愿景：** 构建一个 AI 驱动的智能投研数据平台，整合多源金融数据、AI Agent 分析能力与可视化展示，为投资者提供股票、产业链、热点、资金流、集合竞价等维度的研究支持。

## 2. 项目结构

**⚠️ 重要：AI 智能体在执行任何任务前，必须先了解完整的技术栈和项目组织方式。**

AI Invest Assistant 遵循前后端分离的现代 Web 应用架构。完整的技术栈和文件树结构如下：

### 技术栈概览

- **前端**: React 18.3+ + TypeScript 5.4+ + Vite 5.2+ + React Router 6.23+ + TanStack Query + Zustand + ECharts + AntV/G6 + D3 + Tailwind CSS
- **后端**: Python 3.10+ + FastAPI 0.111+ + SQLAlchemy 2.0+ + Alembic + Pydantic 2.7+ + LangChain/deepagents
- **数据存储**: PostgreSQL/TimescaleDB + Redis + Elasticsearch + COS（S3 兼容对象存储）
- **消息队列**: Celery + Redis
- **部署**: Docker + Docker Compose + 腾讯云 SCF（SPA + API 同源一体镜像）+ 轻量服务器（数据与采集任务）+ COS（文件）

### 核心模块

- **数据采集**: A 股行情、产业链、热点、资金流、集合竞价等数据采集器
- **AI Agent**: 基于 YAML 配置驱动的 Skill 执行与 Agent 调度，支持 OpenAI / Anthropic 协议与 MCP 工具
- **可视化前端**: 大盘、产业链、个股、热点、资金流、集合竞价、研报、管理后台等页面
- **共享层**: `shared/` 目录提供前后端共用的 API 类型与端点常量

### 完整目录结构

请见文档：

- [docs/arch/](./docs/arch/) — 架构设计（终态方案）
- [docs/plan/development-plan.md](./docs/plan/development-plan.md) — 功能开发计划（批次与状态真相源）

### 各目录 AI 上下文

| 目录 | 文件 | 说明 |
|------|------|------|
| `backend/` | [CLAUDE.md](backend/CLAUDE.md) | Python 规范、uv 工具链、FastAPI 分层架构、类型检查标准 |
| `web/` | [CLAUDE.md](web/CLAUDE.md) | 前端技术栈、npm 命令、构建流程 |
| `shared/` | - | 前后端共享类型与常量，保持轻量，禁止引入框架依赖 |

## 3. 通用编码规范与 AI 指令

### 通用指令

- 你最重要的工作是管理自己的上下文。在规划变更前，务必先阅读相关文件。
- 更新文档时，保持更新简洁明了，防止内容冗余。
- 编写代码遵循 KISS、YAGNI 和 DRY 原则。
- 有疑问时遵循经过验证的最佳实践。
- 未经用户批准不要提交到 git。
- 不要运行任何服务器，而是告诉用户运行服务器进行测试。
- 优先考虑行业标准库/框架，而不是自定义实现。
- 永远不要模拟任何东西。永远不要使用占位符。永远不要省略代码。
- 相关时应用 SOLID 原则。使用现代框架特性而不是重新发明解决方案。
- 对想法的好坏要坦率诚实。
- 让副作用明确且最小化。
- 设计数据库模式要便于演进（避免破坏性变更）。

### 文件组织与模块化

- 默认创建多个小而专注的文件，而不是大而单一的文件
- 每个文件应该有单一职责和明确目的
- 尽可能保持文件在 350 行以内 - 通过提取工具、常量、类型或逻辑组件到单独模块来拆分大文件
- 分离关注点：工具、常量、类型、组件和业务逻辑到不同文件
- 优先组合而非继承 - 只在真正的 'is-a' 关系中使用继承，在 'has-a' 或 行为混合时优先组合
- 遵循现有项目结构和约定 - 将文件放在适当目录。必要时创建新目录并移动文件。
- 使用定义明确的子目录保持组织和可扩展性
- 用清晰的文件夹层次和一致的命名约定构建项目
- 正确导入/导出 - 为可重用性和可维护性而设计

### 安全优先

- 永远不要信任外部输入 - 在边界处验证一切
- 将秘钥保存在环境变量中，永远不要在代码中
- 记录安全事件（登录尝试、认证失败、速率限制、权限拒绝），但永远不要记录敏感数据（令牌、个人信息）
- 在 API 网关级别认证用户 - 永远不要信任客户端令牌
- CORS 配置：生产环境必须限制具体域名，不允许 `allow_origins=["*"]`
- 在存储或处理前清理所有用户输入

### 错误处理

- 使用具体异常而不是泛型异常
- 始终记录带上下文的错误
- 提供有用的错误消息
- 安全地失败 - 错误不应该暴露系统内部

### 状态管理

- 每个状态片段有一个真相来源
- 让状态变更明确且可追踪
- 缓存失效策略要明确

### API 设计原则

- 薄路由、重服务的分层架构
- 路由层只处理 HTTP 逻辑（参数验证、响应格式、状态码、异常转换）
- 业务逻辑在服务层实现
- 正确使用 HTTP 状态码
- 使用一致的 JSON 响应格式
- 列表端点支持分页

## 4. AI 功能交互范式（新增 AI 功能必须遵循）

页面级 AI 生成统一走「侧边栏 Agent 触发 + page_event 回写」；定时自动化走「Celery → internal 采集器 → 服务层」。
禁止为 AI 生成新增阻塞式 HTTP 端点（分钟级长任务会被代理 504 中断，且用户看不到过程）。

### 路径一：前端手动触发（侧边栏 Agent）

1. **触发**：页面按钮调 `useAssistantStore.getState().sendQuestion(prompt)`，打开侧边栏并预置问题（范本 `web/src/pages/Dashboard/components/LimitUpSection.tsx` / `AiReviewSection.tsx`）
2. **执行**：助手 agent 按 `skills/<skill-id>/SKILL.md` 取数分析（工具集见 `backend/app/agent/tools/__init__.py` 的 `build_assistant_tools()`）
3. **落库**：分析完成调用 `persist_*` 工具写库，工具返回值携带 `__event__`（用 `page_event("<domain>.complete", **fields)` 构造，见 `backend/app/agent/tools/page_event.py`）
4. **回写**：事件经 SSE 送到前端；`web/src/components/assistant/pageEvents.ts` 的 `PAGE_EVENT_DEFINITIONS` 是唯一映射点（snake_case 字段 parse 为 camelCase + 查看按钮文案 + `path` 结果页路由——会话内查看按钮据此导航，用户在任何页面触发都能直达）
5. **刷新**：页面用 `usePageAssistantResult('<domain>.complete', cb)` 订阅，回调内 `invalidateQueries` 刷新数据 + `message.success` 并返回 true；面板关闭时用 panelOpen effect 复位"生成中"状态

### 路径二：定时自动化（Celery 定时任务）

- cron 声明在 `collector_task` 表（seed：`docker/database/init-scripts/03-seed.sql`，小时均为北京时间，如 `limit_up_ai_review_1630` = `30 16 * * 1-5`）
- 链路：celery beat → collector runtime `run_task` → `TASK_SPECS` 该任务的 `internal` 渠道（`backend/collector/runtime/registry.py`）→ `backend/collector/spiders/<skill>_*.py` 调服务层生成函数（如 `limit_up_ai_service.generate_attribution`）
- 服务层负责 redis 并发锁 + 缓存优先（已生成直接返回）；输入数据未就绪抛 `ReviewInputDataNotReadyError` 由定时任务退避重试
- 两条路径共用同一 SKILL.md 与服务层，落库同 skill_id（新行即最新），手动与定时结果互不冲突

### 新增一个 AI 功能的接线清单

- 后端：`skills/<id>/SKILL.md`（触发条件 / allowed-tools 含 persist 工具 / 输出 Schema）→ persist 工具（返回 `__event__`）→ 注册进 `build_assistant_tools()` → `TASK_SPECS` 加 internal spec + seed cron → 服务层加锁与缓存
- 前端：`stores/assistant.ts` 的 `PageAssistantResult` 联合类型加分支 → `pageEvents.ts` 注册表加一条（必填 parse / actionLabel / path 导航目标）→ 页面 `usePageAssistantResult` 订阅

约定：事件类型命名 `<domain>.complete`；事件字段 snake_case；SKILL.md 的 allowed-tools 列出两条路径工具的并集（含 persist 工具）；persist 工具只注入助手对话路径，定时路径直接调服务层；服务层禁止顶层导入 `app.agent.tools / skills / runtime`（函数内延迟导入，`app.agent.core` 纯配置叶可顶层导入），工具层可导入服务层。

## 5. 任务完成后协议

完成任何编码任务后，遵循此检查清单：

### 1. 类型安全与质量检查

- 根据所在目录的 CLAUDE.md 运行对应的类型检查命令
- 确保测试通过

### 2. 代码质量检查

- 根据所在目录的 CLAUDE.md 运行对应的格式化/ lint 工具
- 检查是否有未使用的导入或变量
- 确保所有新增功能都有相应的测试覆盖

### 3. 验证

- 确保所有类型检查通过后再认为任务完成
- 如果发现类型错误，在标记任务完成前修复它们
- 确保 API 端点的输入验证和错误处理正确
- 验证数据库迁移脚本的正确性

### 4. 文档更新

- 更新相关 API 文档（如有需要）
- 确保代码注释和文档字符串保持最新
- 更新架构文档中的相关信息

# 重要指令提醒

按要求做；不多不少。
除非绝对必要以实现目标，否则永远不要创建文件。
始终优先编辑现有文件而不是创建新文件。
除非用户明确要求，否则永远不要主动创建文档文件（*.md）或 README 文件。
