# 多 Agent 中心（Agent Hub）实现方案

> 状态：决策点已全部拍板（§3，D21-D26），待实施。
> 2026-09-26 需求：模拟管理页升级为「贾维斯总览 + Agent 详情」两级结构，
> 后端从单交易 Agent 演进为多 Agent 架构。
> 上位方案：`paper-trading-plan.md`（D1-D20，平台层与单 Agent 闭环）；
> 本方案承接其后，所有单 Agent 假设按本方案重构。
> 分支：`feature/multi-agent-hub`（自 develop，前置：`feature/trading-agent-quality-fixes` 先合入）。

## 1. 背景与现状

- 需求（用户 2026-09-26 提出）：
  1. `web-api` 镜像命名不合理，需改名；
  2. 模拟管理页改为「先总览后详情」：进入页面先呈现系统中所有 Agent——
     腾讯贾维斯风格的仿真平面图 + 动画（忙碌工作的 Agent 有动态效果），
     点击 Agent 节点才进入现有详情（交易计划/复盘/记忆等）；
  3. 多 Agent 演进路线：当前短线 Agent → 未来长线 Agent → M60（60 分钟波段）Agent；
  4. 每个 Agent 有介绍：策略、风格、使用模型；
  5. 总览页同时呈现各 Agent「正在做什么 / 接下来做什么」。
- **架构评估结论（现状不支持多 Agent，须动数据模型）**：
  - `trading_agent_config` CHECK(id=1) 单例（models/paper_trade.py）；
  - `paper_trade_account.is_agent` 部分唯一索引——数据库层面禁止第二个 agent 账户；
  - `agent_stock_selection` / `agent_trade_plan` / `agent_memory` 无 agent 维度，
    现有唯一约束跨 Agent 必然冲突；
  - `user_watchlist_group.owner_type='agent'` 平台级单例分组；
  - `/trading-agent` 全部 10 个端点、7 个专属工具、2 个 spider（daily-plan / review）
    均无 agent 参数；`assistant_session.agent_type` 为自由字符串（可承载 agent_key）。

## 2. 目标与非目标

**目标**

1. **多 Agent 基础设施一次到位**：注册表 + 全部数据表 agent 维度 + 服务/工具/运行时/
   定时任务/API 全链路参数化；后续新增 Agent = 注册行 + 指定账户 + 策略 prompt，零迁移。
2. **单激活交付**：本批仅 `short-line`（短线）为 active 执行；`long-line`、`m60`
   注册为 planned（总览幽灵节点展示，不参与执行）。
3. **贾维斯总览页**：中心市场核心 + 轨道 Agent 节点雷达 HUD（Canvas 2D 动画）+
   活动时间轴（正在做/接下来），点击节点进详情。
4. **详情页参数化**：现有 TradingAgent 页全部功能按 agentKey 路由参数工作，
   顶部新增介绍卡（策略/风格/模型）。

（镜像改名 `web-api → web` 已随质量优化 PR #84 先行落地，不在本方案范围。）

**非目标（后续批次）**

- Agent CRUD 管理端点（本批 seed-only，新 Agent 手工 SQL 注册）；
- 长线 / M60 Agent 的策略 prompt、方法论源与激活上线；
- 盘中自主执行（迭代 19）——直接建在本批多 Agent 基座上；
- 经验沉淀自动闭环（迭代 20）——同上。

## 3. 决策点

- **D21 注册表取代单例**：新表 `trading_agent`（agent_key 自然主键）承载
  原 `trading_agent_config` 全部配置 + 介绍/展示字段，`DROP TABLE trading_agent_config`
  不留兼容层；消费方一次性全部改点。
- **D22 is_agent → agent_key**：`paper_trade_account` 以可空 `agent_key` FK 取代
  `is_agent` 布尔（用户账户 NULL，agent 账户唯一绑定注册行）；部分唯一索引随迁。
- **D23 数据表 agent 维度**：三张 agent 表 + agent 自选分组加 `agent_key` 并重建
  唯一约束；存量行回填 `short-line`。
- **D24 API 路径参数**：`/trading-agent/{agentKey}/...`（弃 query 参数方案）——
  REST 语义清晰、缓存键干净、DELETE/PUT 无歧义；新增 `GET /trading-agent/agents` 总览聚合。
- **D25 会话身份**：`assistant_session.agent_type` 加宽至 VARCHAR(32)，
  交易 Agent 线程直接存 agent_key（`'trading'` 存量行迁移为 `'short-line'`）；
  运行时按注册表校验，'assistant' 之外一律走交易 Agent 分流。
- **D26 贾维斯视觉**：中心核心 + 轨道雷达形态（Canvas 2D 自绘，requestAnimationFrame），
  弃 ECharts/G6（图表达场景不适合 HUD 动效）；未上线 Agent 幽灵节点 + 预告卡
  （点击弹简介，不可进入）。
- **D27 人设与专属 Skill**（2026-09-26 追加）：每 Agent 三层个性化——
  ① 会话人设：`prompts/agents/trading_agent_<agent_key 转下划线>.yaml`，
  注册表 `prompt_id` 分流（机制 D21 已备），共享 `trading_agent.yaml` 删除；
  ② 计划作业 Skill：`skills/trading-<agent_key>/`（SKILL.md 作业方法论 +
  prompt.yaml 计划契约），登记 BUILTIN_SKILLS 新增 `trading` 场景，
  `agent_plan_service` 按 agent_key 装载（共享 `agent_daily_plan.yaml` 删除，
  缓存 skill_id 随之 per-agent）；③ 复盘人设：共享 `trading_review.yaml` 契约
  不动，user_prompt 注入注册行人设段。平台硬纪律（ask_user 确认/风控转述等）
  三份人设保持一致。trading 技能不出现在助手技能广场（`list_skills` 与
  `skill_sync` 过滤）——它们是 Agent 内部作业程序，助手对话不可调用。
- **D28 验收修复与扩展性定版**（2026-09-26 追加，分支 `feature/agent-hub-ux-fixes`）：
  ① 注册表加 `plan_cadence` / `review_cadence`（daily/weekly/monthly）——spider 与
  总览「接下来」同语义门控（daily 每交易日；weekly/monthly 仅周期末，复用
  `is_last_trading_day_of_week/month`）；② **任意状态可编辑**：`update_agent` 白名单
  开放 `status`（仅 active/disabled，planned 为种子初始态不可回置）与人设四字段，
  停用 = 雷达隐藏 + 不参与调度；③ 雷达仅画 active 节点，planned 幽灵节点删除，
  管理入口改总览页「Agent 管理列表」（含启用 Switch）；布局改实测容器像素椭圆
  （Canvas 与 HTML 标签层共用，修复单节点越界裁剪与双层错位）；④ **人设运行时
  注入**：会话 system_prompt 头部拼「你的身份（注册表）」段并入 fingerprint——
  编辑名称/标语/风格/策略即时生效（YAML 人设文件降级为硬纪律+工作流骨架，
  与注册表不再重复）；计划 user_prompt 同步注入；⑤ plans 端点包装
  `{tradeDate, nextTradeDate, plans}` 次日语义 + 标题显示所选日期与交易时段；
  ⑥ agent 自选行复用「我的自选」样式（名称/代号/分时缩略图/现价涨跌幅）；
  ⑦ **扩展性定版：新 Agent = INSERT 注册表一行**——计划技能 `trading-<key>` 不存在
  时 fallback `skills/trading-default/`（共享作业程序）；prompt_id 可指向任意既有
  人设模板；前端 `short-line` 默认值兜底全部清除（缺路由参数跳回总览），
  名称/策略/频率后续均 UI 配置，零代码新增。

## 4. 数据模型

**注册表 `trading_agent`**（迁移 + init-scripts 同步，幂等 SQL）：

| 列 | 类型 | 说明 |
|---|---|---|
| agent_key | VARCHAR(32) PK | URL 安全自然键（short-line / long-line / m60） |
| name | VARCHAR(64) | 展示名（短线猎手 / 长线舵手 / 60分钟波段） |
| tagline | VARCHAR(128) | 一句话定位 |
| strategy_desc | TEXT | 策略介绍（介绍卡 + 预告卡用） |
| style_desc | VARCHAR(64) | 风格标签（激进/稳健/…） |
| llm_config_id | INT FK llm_config | 对话/结构化输出模型 |
| methodology_source_id | BIGINT FK kb_source | 方法论基座 KB 源（KB 直读双层注入沿用） |
| risk_max_position_pct / risk_max_total_pct / risk_max_daily_orders | NUMERIC/INT | 风控三参数（原 config 迁移） |
| auto_exec_enabled | BOOLEAN | 自主执行总闸 |
| status | VARCHAR(16) chk | active / planned / disabled |
| plan_cadence / review_cadence | VARCHAR(16) chk | daily / weekly / monthly（D28，计划与复盘生成频率） |
| sort_order | INT | 总览排布 |
| prompt_id | VARCHAR(64) | `prompts/agents/<prompt_id>.yaml`，per-agent 人设（D27：short/long/m60 三份） |
| accent_color | VARCHAR(16) | 总览节点主色 |
| created_at / updated_at | timestamptz | 审计 |

种子：`short-line`（active，配置自原 trading_agent_config 行迁移）、
`long-line`（planned）、`m60`（planned）。

**agent 维度迁移**（同一迁移文件）：

1. `paper_trade_account`：DROP is_agent 唯一索引 → 加可空 `agent_key` FK →
   回填 `agent_key='short-line' WHERE is_agent` → 部分唯一索引
   `(agent_key) WHERE agent_key IS NOT NULL` → `DROP COLUMN is_agent`。
2. `agent_stock_selection` / `agent_trade_plan` / `agent_memory`：加 `agent_key`
   NOT NULL FK（回填 short-line），唯一约束重建为含 agent_key：
   `(agent_key, trade_date, stock_code)` / `(agent_key, plan_date, stock_code, plan_type)` /
   `(agent_key, source_result_id, title)`。
3. `user_watchlist_group`：加可空 `agent_key`，部分唯一
   `(owner_type, agent_key) WHERE owner_type='agent' AND agent_key IS NOT NULL`。
4. `assistant_session.agent_type` VARCHAR(16)→32；
   `UPDATE SET agent_type='short-line' WHERE agent_type='trading'`。

## 5. 后端改造

**服务层**

- 新 `app/services/trading/agent_registry.py`：`get_agent`（404）/ `list_agents(statuses)` /
  `get_active_agents` / `update_agent_config`——吸收并删除 `agent_config.py`。
- `resolve_agent_account(session, agent_key)`（account_service）；designate/revoke 按
  agent_key 绑定/解绑；is_agent 消费点全清（schemas/paper_trade、admin/paper_trade、
  paper_trade 路由、paper_trade_sync、paper_trade_service、agent_trade_service、errors 语义）。
- plan / review / trade / memory / methodology / plan_ops 全链路穿 `agent_key`；
  `_input_hash(agent_key, account_id, trade_date)`（缓存按 Agent 分离）；
  `_ensure_agent_group(session, agent_key)` 每 Agent 一个自选分组。

**工具与运行时**

- `build_trading_tools(agent_key)` 闭包绑定，`TOOLS_VERSION = 4`；
- `get_trading_agent(agent_key)`：模型/方法论按注册行、fingerprint 含 agent_key+prompt_id、
  prompt 走 `loader.load("agents", row.prompt_id)`；
- `runs.py` / `threads.py`：白名单 → 注册表校验（'assistant' + active agent_key），
  admin 门禁保留。

**定时任务**

- `collector/spiders/agent_daily_plan.py`、`paper_trade_review.py` 循环
  `get_active_agents()`（planned 天然跳过）；单 Agent try/except 隔离，
  结果聚合单条 CollectResult（partial=部分失败，message 列明细）；空集 SKIPPED。
- `runtime/specs/trading.py` 不变。

**API**（prefix `/trading-agent`，路径参数）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/agents` | 总览聚合（新，见 §6） |
| GET/PUT | `/{agentKey}/config` | 任意状态可写（D28）；PUT 可携 status/name/人设/频率 |
| GET | `/{agentKey}/review · /dates · /plans · /selections · /memories` | planned 可读；plans 返回 `{tradeDate, nextTradeDate, plans}`（D28） |
| POST | `/{agentKey}/plans/{id}/cancel` | active |
| DELETE | `/{agentKey}/selections/{id}` | active |
| PUT | `/{agentKey}/memories/{id} · /memories/{id}/status` | active |

**总览聚合服务**（新 `agent_overview_service.py`）

- 每 Agent：profile（name/tagline/strategy_desc/style_desc/accent_color/status）+
  模型信息（join llm_config）+ 当日计数（active/triggered 计划数、agent 账户持仓数）+
  近期活动（plan `triggered_at`、review 生成时间、`collector_log` 相关任务行）+
  下次任务时刻（复用 `app/services/collector/cron_utils.py` croniter 展开 +
  `trade_calendar_service` 交易日过滤；后端算好绝对时刻，前端纯渲染）。

## 6. 前端设计

**路由**：`/trading-agent` index → `AgentOverview`（新）；`/trading-agent/:agentKey` →
现有 `TradingAgent`（参数化）。侧边栏「模拟管理」入口不变（落总览页）。

**总览页（贾维斯 HUD，实现用 frontend-design skill）**

```
pages/AgentOverview/
  AgentOverview.tsx      # 30s refetchInterval 轮询 GET /trading-agent/agents
  ├─ AgentRadarCanvas.tsx  # rAF Canvas 2D：科技网格底、雷达扫描线、中心市场核心、
  │                        # 轨道 Agent 节点（busy 脉冲光环加速；planned 幽灵暗色半透明）、
  │                        # 核心↔节点数据粒子流；DPR 适配 + ResizeObserver
  ├─ AgentNodeLabels.tsx   # HTML 覆盖层：节点名卡；active 点击导航详情，planned 弹预告卡
  └─ ActivityTimeline.tsx  # 底部时间轴：正在做 / 接下来（总览载荷）
```

**详情页**：顶部介绍卡（策略/风格/模型，accent_color 点缀）+ 原 7 tab 功能全部按
agentKey 工作（今日计划 / AI 复盘 / 记忆 / 配置 / 会话等）；会话线程创建携带 agent_key。

**shared 契约**：ENDPOINTS 的 tradingAgent 系列改 `(agentKey) => ...` 工厂 +
`tradingAgentAgents`；`shared/types/tradingAgent.ts` 加 `TradingAgentProfile /
AgentOverviewItem / AgentOverviewResponse`，载荷加 agentKey；queryKeys tradingAgent 族
加 agentKey 段；`AssistantAgentType` 放宽为 string（注册表驱动）。

**暗色主题纪律**：border-white/10 + bg-white/[0.03]，禁硬编码浅色。

## 8. 提交序列（分支 `feature/multi-agent-hub`，每提交门禁绿）

0. 方案文档（本文档 + development-plan.md 迭代行）——首提交
1. 迁移 + 模型 + 注册表服务 + 全服务 agent_key 穿线 + 单测更新
2. 工具 + 运行时 + 会话分流（TOOLS_VERSION=4）+ 单测
3. spider 多 Agent 循环 + 单测
4. API 路径参数 + 总览聚合端点 + API 测试
5. 前端详情页参数化 + 介绍卡 + shared 契约
6. 贾维斯总览页（Canvas + 时间轴 + 轮询）

## 9. 验收

1. 门禁：backend `uv run mypy app/ && uv run pytest -m unit && uv run ruff check .`；
   web `npm run typecheck && npm run lint && npm run test:unit && npm run build`。
2. 本地栈端到端：
   - 迁移先于镜像（DDL 后重启 web/worker/beat——asyncpg 语句缓存纪律）；
   - `/trading-agent` 总览：雷达动画 3 节点（短线 busy / 长线、M60 幽灵）+ 活动时间轴；
   - 点短线节点进详情：介绍卡 + 原 7 tab 功能回归 + 会话下单链路正常；
   - 手动触发 `agent_daily_plan_1900`：落库行带 agent_key='short-line'，重跑命中缓存；
   - planned Agent 详情路由直接访问被拒（404/422）。
3. 测试重点：registry 服务、resolve_agent_account(agent_key)、plan/review 服务
  （mock run_structured）、spider 双 Agent 循环隔离、API 路径参数、threads 注册表校验、
  agent 自选分组不被用户删除级联（存量单测改 agent_key 维度）。

## 10. 风险与部署纪律

- `ai_analysis_result` 旧缓存行 input_hash 不含 agent_key → 一次性重生成，可接受；
- `assistant_session.agent_type` 数据迁移须与新代码同窗口上线（旧代码拒绝 'short-line'）；
- 迁移后 asyncpg 预编译语句失效一次 → 先迁移后换镜像并重启；
- watchlist 前端/查询对 owner_type='agent' 单例的隐含假设需 grep 清理。
