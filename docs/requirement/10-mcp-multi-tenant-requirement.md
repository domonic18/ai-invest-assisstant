# MCP 多租户能力开放 需求文档

> 版本：V1.0（2026-10-29 定稿）　状态：P0 已交付（2026-10-29）；P1 自选股读写已交付（2026-10-30），财报三件套 / 调用审计 / 限流待实现
> 定位：把平台既有的只读投研能力以 MCP（Streamable HTTP）协议开放给外部 Agent
> 客户端（Claude Code / WorkBuddy / 飞书投资助手），以 **API Key 多租户** 隔离身份与数据。
> 上位文档：[04-ai-agent.md](../arch/04-ai-agent.md)（§MCP Server 终态）、
> [05-account-quota-requirement.md](./05-account-quota-requirement.md)（API-KEY 路径预留）

## 1. 文档概述

### 1.1 背景与目的

平台已沉淀五类可复用的投研能力：大盘/板块/个股异动、抖音大V散户情绪、交易 Agent
（账户、计划、复盘、选股）、知识库与方法论、财报。这些能力目前只服务站内页面与站内
助手，外部 Agent 无法直接调用。

本需求在 `/api/v1/mcp` 暴露一个 **Streamable HTTP MCP Server**，把上述能力以工具形式
开放。外部客户端（飞书机器人背后的 Claude Code 等）凭 **个人 API Key** 接入，看到的
数据范围与站内同用户一致。

### 1.2 适用范围

- 面向对象：平台注册用户（管理员签发 API Key），首期仅本人使用，后续开放多用户。
- 覆盖能力：只读投研数据 + 知识库检索（P0）；自选股读写与财报三件套（P1）。
- **不开放**：下单/撤单、制定/取消交易计划、触发复盘生成、任何 LLM 生成入口
  （分钟级任务不适合 MCP 同步调用，且会引入未计量的 LLM 成本）。

### 1.3 术语

| 术语 | 含义 |
|------|------|
| MCP | Model Context Protocol，Agent 客户端发现与调用工具的开放协议 |
| Streamable HTTP | MCP 现行远程传输（单端点、支持 SSE 流式响应） |
| API Key | 平台签发的个人访问凭证，格式 `inv_<8位前缀>_<32位随机>` |
| Scope | API Key 的权限范围（如 `trading:read`），工具调用前校验 |
| 多租户 | 不同 API Key 归属不同 `user_id`，用户态数据按用户隔离 |

## 2. 现状（2026-10-29 代码实证）

| 项 | 现状 | 位置 |
|---|---|---|
| MCP 出口 | 仅占位路由（`GET /mcp/tools` 返回空） | `api/v1/mcp/server.py` |
| 认证 | 仅 JWT（OAuth2 password），无 PAT / API Key | `dependencies/__init__.py` |
| 能力沉淀 | 服务层与站内 LangChain 工具已具备全部读取能力 | `services/*`、`agent/tools/*` |
| 架构预留 | arch/04 声明平台经 fastmcp 对外暴露 MCP Server | `docs/arch/04-ai-agent.md` |
| 配额 | 站内 AI 入口走 `quota_service.precheck`；API Key 路径未实现 | `services/quota/*` |

结论：无需新建业务能力，工作集中在 **协议出口、凭证体系、工具封装** 三件事。

## 3. 目标与非目标

**目标**

1. 一个可被标准 MCP 客户端（含 Claude Code）直连的 Streamable HTTP 端点；
2. 个人 API Key 签发/吊销/过期，校验按哈希查库，明文只出现一次；
3. 工具级 Scope 校验，越权调用返回明确错误而非静默空数据；
4. 用户态数据（大盘复盘个人编辑版、个股异动自选标注）按 Key 所属用户返回；
5. 复用既有服务层，工具层只做协议适配与输出裁剪。

**非目标**

- 不做 OAuth 2.1 授权服务器（静态 Bearer Token 足够，客户端以 Header 携带）；
- 不做交易写操作（下单/撤单/计划/复盘生成）；自选股写入按 P1 开放（见 §5.2）；
- 不做独立部署（挂载在现有 FastAPI 应用，共享连接池与配置）；
- 不在 P0 做配额计量（当前无 LLM 调用，仅 KB 检索 embedding 成本，P1 再评估）。

## 4. 总体设计

### 4.1 部署形态

```
MCP 客户端 ──Bearer API Key──▶ Caddy ──▶ FastAPI (:9000)
                                        ├─ /api/v1/*  现有 REST
                                        └─ /api/v1/mcp FastMCP Streamable HTTP
```

- 单 uvicorn 进程，FastMCP 的 `session_manager` 在 FastAPI lifespan 内运行；
- 挂载方式：`app.mount("/api/v1", mcp_asgi_app)`，FastMCP 内部路径 `/mcp`，
  最终端点 **`https://<host>/api/v1/mcp`**（无尾斜杠）；
- 关闭 DNS rebinding 校验（请求先经 Caddy，Host 为公网域名）；
- `stateless_http=True`：不依赖会话粘滞，为未来多 worker 留余量。

### 4.2 认证与多租户

**Token 格式**：`inv_<8位hex前缀>_<32位随机串>`。

**存储**：`user_api_key` 表只存 `key_hash = HMAC-SHA256(pepper, token)`，前缀明文用于列表
展示。pepper 取 `MCP_API_KEY_PEPPER`，未配置时回退 `SECRET_KEY`（生产必须显式配置，
避免轮换 JWT 密钥导致 Key 全体失效）。

**校验链**（每次 MCP 请求）：

1. 解析 `Authorization: Bearer <token>`；
2. 按 hash 精确查 `user_api_key`，要求 `revoked_at IS NULL` 且未过期；
3. 关联用户要求 `is_active` 且 `status='approved'`；
4. 命中后把 `user_id` / `api_key_id` / scopes 写入 MCP 访问令牌上下文；
5. `last_used_at` 节流更新（默认 5 分钟）。

**Scope 清单**：

| Scope | 覆盖工具 |
|---|---|
| `market:read` | 大盘复盘、板块异动、个股异动、散户情绪 |
| `trading:read` | 交易账户、计划、复盘、选股 |
| `kb:read` | 知识库检索 |
| `watchlist:read` | 自选股分组与股票读取（P1 已上线） |
| `watchlist:write` | 自选股分组与股票增删改（P1 已上线，未含批量移动以外的高级操作） |
| `reports:read` / `reports:collect` | 财报查询 / 触发补采（待实现） |

### 4.3 数据归属

| 数据 | 归属 | MCP 行为 |
|---|---|---|
| 大盘复盘 | 用户编辑版优先，回退共享 base | 按 Key 用户读取（`get_market_review`） |
| 个股异动 | 共享检测结果 + 个人自选标注 | `is_watchlist` 按 Key 用户计算 |
| 自选股分组 | 用户私有 | 按 Key 用户读写（P1 已上线） |
| 交易 Agent 账户/计划/复盘/选股 | 平台共享（Agent 专属账户） | 只读，不受用户隔离 |
| 知识库 / 财报 / 行情异动 | 平台共享 | 只读 |

### 4.4 兼容性说明（cc-connect）

cc-connect 一个 project 对应一个飞书机器人 + 一套静态 MCP 配置，因此「一个机器人服务
多个用户」在当前客户端形态下无法按消息来源切换 API Key。多用户接入有三条路径（P2 决策）：
①一用户一 project/bot；②平台自建飞书机器人，按 `open_id` 映射平台用户后注入 Key；
③客户端支持按会话传 Header。P0 先完成服务端多租户底座，不阻塞单用户上线。

## 5. 工具契约（P0：9 个只读 + P1：6 个自选股工具）

通用约定：日期参数 `YYYY-MM-DD`，缺省取最新交易日；所有工具返回 JSON 对象，
业务性失败返回 `{"error": "..."}`，鉴权/参数错误以 MCP ToolError 返回。

### 5.1 P0 只读工具

| 工具 | Scope | 参数 | 返回要点 |
|---|---|---|---|
| `get_market_daily_review` | market:read | `trade_date?` | `trade_date` / `sections[{key,title,content}]` / `model` / `generated_at` / `edited`；未生成返回 `not_ready` |
| `get_sector_anomaly` | market:read | `trade_date?` / `limit=20` | `total`、`items[{sector_name,change_pct,amount_ratio,anomaly_types,strength,attribution_summary}]` |
| `get_stock_anomaly` | market:read | `trade_date?` / `limit=20` | `total`、`items[{code,name,change_pct,anomaly_types,sectors,strength,is_watchlist}]` |
| `get_social_sentiment` | market:read | `trade_date` | 多空中性分布、近 7 日净多空、代表观点、`sample_insufficient` |
| `get_trading_account` | trading:read | `agent_key?` | 资金概况、持仓、未结委托 |
| `list_trading_plans` | trading:read | `agent_key?` | 当日计划列表与状态机 |
| `get_trading_review` | trading:read | `agent_key?` / `period?` / `trade_date?` / `scope?` / `start_date?` / `end_date?` | 分层复盘全文；未生成返回 `not_ready` |
| `get_trading_selections` | trading:read | `agent_key?` | 当前选股清单（代码/理由/置信度/日期） |
| `search_knowledge_base` | kb:read | `query` / `source?` / `chapter?` / `point_type?` / `include_media=false` | 知识卡片 + 原文片段 + 可溯源引用 |

`agent_key` 缺省取配置 `MCP_DEFAULT_AGENT_KEY`（默认 `short-line`）。

### 5.2 P1 自选股读写工具

写操作只作用于 Key 所属用户的自选股（与站内个人设置同源），默认分组不可改名或删除。

| 工具 | Scope | 参数 | 返回要点 |
|---|---|---|---|
| `list_watchlist_groups` | watchlist:read | — | `groups[{id,name,is_default,ai_review_enabled,stock_count}]` |
| `get_watchlist` | watchlist:read | `group_name?` | 分组及 `stocks[{stock_code,stock_name,market,group_id,added_at}]` |
| `add_watchlist_stocks` | watchlist:write | `stock_codes[]` / `group_name?` / `new_group_name?` / `tags?` | `created` / `duplicated` / `invalid`（单次 ≤50，分组参数互斥） |
| `remove_watchlist_stocks` | watchlist:write | `stock_codes[]` / `group_name?` | `removed` / `not_found` / `mismatch[{stock_code,actual_group}]` |
| `move_watchlist_stock` | watchlist:write | `stock_code` / `target_group_name` | 移动结果（新分组与来源分组 id） |
| `manage_watchlist_group` | watchlist:write | `action`(create/rename/delete) / `name` / `new_name?` / `delete_items=false` | 分组信息或删除结果 |

## 6. 配置项

| 配置 | 默认 | 说明 |
|---|---|---|
| `MCP_ISSUER_URL` | `https://invest.17aitech.com` | FastMCP AuthSettings 必填占位（不做 OAuth 发现） |
| `MCP_API_KEY_PEPPER` | 空 → 回退 `SECRET_KEY` | Key 哈希 pepper，生产必须显式设置 |
| `MCP_DEFAULT_AGENT_KEY` | `short-line` | 交易类工具缺省 Agent |
| `MCP_API_KEY_LAST_USED_THROTTLE_SECONDS` | 300 | `last_used_at` 写入节流 |

## 7. 管理接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/admin/api-keys/?user_id=` | 列出 Key（不回显 hash 与明文） |
| POST | `/api/v1/admin/api-keys/` | 签发，响应含一次性明文 `token` |
| DELETE | `/api/v1/admin/api-keys/{id}` | 吊销（置 `revoked_at`，幂等） |
| GET | `/api/v1/users/me/api-keys/` | 个人设置：列出本人 Key |
| POST | `/api/v1/users/me/api-keys/` | 个人设置：签发（scope 服务端固定，忽略请求体中的 `userId`/`scopes`） |
| DELETE | `/api/v1/users/me/api-keys/{id}` | 个人设置：吊销本人 Key（他人 Key 返回 404） |
| DELETE | `/api/v1/users/me/api-keys/{id}/purge` | 个人设置：删除已吊销的 Key 记录（未吊销返回 400） |

自助签发默认 scope = `market:read` / `trading:read` / `kb:read` /
`watchlist:read` / `watchlist:write`（`API_KEY_SELF_SERVICE_SCOPES`，覆盖已上线的
MCP 工具；已签发的旧 Key 需重新签发才能获得自选股权限）。
前端入口：个人设置 → 「MCP 密钥」（签发后明文只展示一次）。

## 8. 验收标准

1. 未携带/携带错误 Key 请求 `/api/v1/mcp` 返回 401；其余 REST 路由行为不变；
2. 携带有效 Key 完成 MCP `initialize → tools/list → tools/call`，15 个工具均可见
   （9 个只读 + 6 个自选股）；
3. 缺失 Scope 调用对应工具返回明确错误（提示所需 scope），不返回空数据；
4. 两个不同用户的 Key 调用 `get_stock_anomaly` 与自选股工具，`is_watchlist` 与
   分组/股票列表各自独立，写操作互不影响；
5. 吊销或过期后立即 401；`last_used_at` 在节流窗口内只写一次；
6. 大盘复盘读取用户编辑版优先、回退共享 base，与站内 `GET /market/ai-review` 一致；
7. 全部新增单元测试通过，`ruff check` / `mypy app/` 无新增问题。

## 9. 实施批次

- **P0（已交付 2026-10-29）**：`user_api_key` 迁移/模型/服务/管理接口 + MCP 服务端与 9 个只读工具 + 单测。
- **P1**：自选股分组与股票读写（6 个工具，已交付 2026-10-30）；财报三件套、调用审计与 Redis 限流待实现。
- **P2**：cc-connect/飞书机器人接入、端到端验收、WorkBuddy 兼容性验证、多用户开通流程。
