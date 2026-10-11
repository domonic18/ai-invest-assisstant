# 交易 Agent 数据能力补齐计划（行情工具 · 数据补采 · 画线视觉）

> 状态：2026-10-11 立项（用户反馈驱动）。批次 1 方案已定可实施；批次 2 含选型决策点（§6）待拍板。
> 排查结论与本文技术事实均经代码核实，文件行号以当日代码为准。

## 1. 背景与问题

2026-10-11 用户反馈：与交易 Agent（短线猎手，agent_key=short-line）讨论交易计划时，agent 无任何行情/K线工具可用，agent 自查工具清单并向平台侧上报配置缺失。

代码级排查结论：

- 工具注册真相源 `app/agent/tools/trading/__init__.py` `build_trading_tools` 仅 9 工具（账户/下单/撤单/计划/选股/复盘 + ask_user），**无任何行情工具**——与 agent 自述清单逐项吻合
- 系统提示词 `app/prompts/agents/trading_agent_short_line.yaml` 交易纪律第 1 条「下单前必查……再用**行情工具**获取现价」引用了从未注册的工具类别——设计意图（询价后下单）与工具集脱节
- 平台现成个股行情工具早已注册给人工助手（`build_assistant_tools`），交易 Agent 未接入
- 隐性坑：agent 实例缓存指纹含 `TOOLS_VERSION`（见 §2.1），改工具清单必须同步 bump，否则旧实例不重建、改动不生效

## 2. 现状盘点（技术事实）

### 2.1 工具与缓存机制

- `build_trading_tools(agent_key)`：交易 Agent 对话路径唯一工具来源。写工具经 `make_*` 工厂按 agent_key 闭包绑定；只读全局工具为模块级单例，可直接复用
- `app/agent/runtime/trading_agent.py` 实例缓存指纹 = agent_key × prompt_id × 人设 × LLM 出口 × `TOOLS_VERSION` × 方法论源；命中缓存忽略传入工具。**工具集变更须 `TOOLS_VERSION` +1**（当前 4）。bump 后同一线程下一条消息即生效（图实例按消息重建判定），无需新开会话
- 定时路径（选股/计划生成）直调服务层不经工具，本计划不触碰

### 2.2 现成可复用工具池（人工助手已在用，接线零开发）

| 工具 | 能力 | 位置 |
|------|------|------|
| `get_stock_quote` | 现价快照（Redis 实时缺失回退最新日K） | `agent/tools/stock_tools.py` |
| `get_stock_kline` | 日K（OHLC/量/涨跌幅，1-120 条） | 同上 |
| `get_stock_technical` | 预计算技术面文本（均线/通道/拐点信号/周线形态） | 同上 |
| `get_stock_emotion_context` | 个股情绪面（涨停/连板状态、板块资金排名、市场涨停结构） | 同上 |
| `get_stock_fund_flow` | 个股主力资金分档流向 | 同上 |
| `get_trade_calendar` | 当前时间/交易日/最近交易日（数据滞后判定基准） | `agent/tools/market_tools.py` |
| `query_financial_data` | 核心财务指标（毛利率/营收同比/研发占比，库内） | `agent/tools/stock_tools.py` |
| `download_financial_reports` | 触发财报 PDF 采集（异步） | `agent/tools/report_tools.py` |
| `query_financial_reports` | 查询库内财报列表 | 同上 |
| `summarize_financial_report` | 单篇财报 AI 摘要 | 同上 |

### 2.3 数据补采链路

- `collect_market_data(trade_date, symbols)`（`market_tools.py`）：异步派发涨停池/炸板池/跌停池/成交额/板块资金流/指数K线，传 `symbols` 时追加**个股日K**采集（`sina_kline` 原生支持 symbols）——个股K线补采零新增开发
- 财务指标补采：`eastmoney_financial_statement` spider 原生接受 `symbols`；`collector/runtime/runner.py` `_build_task_kwargs` 对**任意任务**统一接受 `symbols` 参数——直接派发 `financial-statement` + `{"symbols": [...]}` 即按股补采，无需改声明表
- 板块K线补采：**暂不做**（2026-10-11 拍板）。`sector-kline` 为全量任务（约 465 板块 × 限速 0.3s，无单板块参数），后续若做需先解决按板块采集粒度

### 2.4 画线与视觉基础设施（批次 2 评估基础）

- 画线体系：用户画线（`UserKlineDrawing`）+ AI 画线组（`AiKlineDrawing`）双图层；`KlineDrawingService` 全 CRUD；前端 `web/src/components/charts/drawing/` 完整图层渲染栈（shapeSpecs/layerRender/coordinates 锚点几何）
- AI「看」画线现状：仅结构化 JSON（`get_kline_drawings`），无视觉通道
- 视觉基础设施已具备：
  - `run_structured(images=[(bytes, media_type)], vision=True)`（`agent/runtime/structured.py`）：KB 截图识别同款单轮视觉路径，vision 槽位独立解析视觉模型出口
  - langchain-core 1.6.0（uv.lock）：支持多模态 ToolMessage——工具可返回 text + image content blocks，图像直进会话上下文
  - `minio_service`（对象存储）与 pillow 已在依赖；playwright + chromium 已在部署（`app/signer/backend.py`）
- 前端聊天消息暂无图片渲染能力（assistant 侧边栏与 TradingAgent 页均未支持）

## 3. 目标与非目标

**目标**

1. 交易 Agent 具备下单前询价能力（现价/日K），提示词纪律与工具集一致
2. 数据滞后时 agent 可自主触发补采：个股日K、个股财务指标、财报 PDF
3. （批次 2）画线结果可渲染为图片，供 AI 视觉查看与自检

**非目标**

- 板块K线补采（已拍板暂缓，见 §2.3）
- 交易 Agent 挂载 skills / subagents / MCP（保持窄域执行体定位，paper-trading-plan D18）
- 定时路径改造；画线写路径改动（现有用户/AI 双图层不变）

## 4. 批次 1：行情查询与数据补采工具接线（方案已定，可实施）

### 4.1 改动清单

1. `app/agent/tools/trading/__init__.py`：
   - `build_trading_tools` 追加 §2.2 全部 10 个现成工具 + `collect_market_data`（个股K线补采入口）
   - `TOOLS_VERSION` 4 → 5
2. 新增 `collect_financial_data` 工具（`app/agent/tools/trading/` 新文件，无 agent_key 绑定）：入参 `stock_codes`（必填）+ `report_types`（可选）→ `dispatch_collector_task("financial-statement", {"symbols": ..., ...})`；返回派发清单与等待提示，文案对齐 `collect_market_data`（异步派发，稍后复查验证）
3. 提示词 YAML 不动——「行情工具」引用随工具到位自动满足
4. 测试：新增 `tests/unit/agent/test_trading_tools.py` 钉死交易工具清单（对齐 `test_assistant_tools` 模式）+ `collect_financial_data` 派发参数断言

### 4.2 数据自愈工作流（由工具描述引导，无需额外编排）

`get_trade_calendar` 确认最近交易日 → 查询工具取数并核对数据日期 → 滞后时 `collect_market_data(trade_date, symbols)` / `collect_financial_data` 派发补采 → 等待入库后重新查询验证（各工具 docstring 已内建该引导文案）

### 4.3 验收

- `uv run mypy app/` / `uv run pytest -m unit` / `uv run ruff check .` 全绿
- 会话实测：让短线猎手查询指定股票现价与近 30 日K线（工具清单中出现且调用成功）
- 自愈实测：手动删除某股最近一日日K → 会话内让 agent 发现数据滞后并自主补采恢复

## 5. 批次 2：画线截图与 AI 视觉查看（下一步，决策点见 §6）

### 5.1 需求描述

在会话中对个股画线（趋势线/射线/水平线/箱体，锚点几何与前端画线体系同构），将画线渲染结果生成截图交由 AI 视觉查看——补上「结构化画线 JSON ↔ 视觉直觉」的验证闭环。价值：agent 画完线亲眼确认落位（是否触及K线、压力位是否成立）；用户画的线 agent 能「看图」而非只读 JSON。

### 5.2 渲染选型（D-V2）

| 方案 | 优点 | 缺点 |
|------|------|------|
| **A. 服务端渲染（推荐）**：pillow 自绘蜡烛+画线（零新增重依赖），或引入 mplfinance | 自主可控、确定性、不依赖前端与登录态，定时路径未来可复用 | 与前端视觉非像素级一致（画线语义一致，可接受） |
| B. Playwright 截真实前端页 | 像素级一致，复用 ECharts + 图层栈 | 需处理路由/登录态/等待渲染；chromium 重；前端改动会破坏截图 |
| C. 前端截图回传（page_event 驱动） | 像素级一致 | 仅用户开页时可行，不适合自主作业 |

方案 A 输入 = 日K序列 + 画线 JSON（锚点映射 date→x / price→y，算法与前端 `coordinates.ts` 同构），输出 PNG bytes。

### 5.3 图像消费路径（D-V3）

- **路径 1（推荐主路径）**：工具返回多模态 ToolMessage（text + image block），图像直进会话上下文，绑定模型亲眼查看。约束：交易 Agent 绑定的模型出口须支持图像输入（anthropic 协议 Claude 系可用；部分 openai 兼容端点不支持）
- **路径 2（降级/补充）**：模型出口不支持视觉时，`run_structured(vision=True)` 走系统视觉槽位独立看图、返回结构化文本结论（KB 截图识别同款机制，零新增基建）；PNG 同时传 minio 返回 URL
- 前端聊天图片渲染（子项，可独立后置）：消息内展示截图，当前前后端均无此能力，需要独立接线

### 5.4 验收草案

- agent 画一条趋势线 → 收到截图 → 复述两锚点日期/价格与线是否触及K线高点的视觉自检
- 用户在网页画线 → agent「看图」描述图中每条线的类型与关键位，与 `get_kline_drawings` JSON 互证

## 6. 决策点记录

| # | 问题 | 选项 | 状态 |
|---|------|------|------|
| D-V1 | 批次 2 画线来源 | a. 仅用户已画线渲染给 AI / b. 仅 agent 会话内自画自看 / c. 两者都做 | 待拍板 |
| D-V2 | 渲染方案 | A 服务端渲染（推荐）/ B Playwright 截页 / C 前端回传 | 待拍板 |
| D-V3 | 图像消费路径 | 路径 1 ToolMessage 直看 / 路径 2 vision 槽位降级 / 双路径（推荐） | 待拍板 |
| D-V4 | 前端聊天图片渲染是否随批次 2 交付 | 随批交付 / 独立后置 | 待拍板 |

## 7. 实施纪律

- 批次 1 独立提交可验收；`TOOLS_VERSION` 与工具清单同一提交，禁止只加工具不 bump
- 批次 2 须先拍板 §6 决策点再动工；渲染器独立模块（`app/services/trading/` 或 `app/services/market/`），不与工具层耦合
- 登记进 `development-plan.md` 待开发表，状态流转按其 §5 维护约定
