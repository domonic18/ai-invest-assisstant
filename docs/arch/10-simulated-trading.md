# 模拟交易与交易 Agent

> 终态运行时架构。需求背景见 [07-simulated-trading-requirement.md](../requirement/07-simulated-trading-requirement.md)
> 与 [09-multi-period-review-requirement.md](../requirement/09-multi-period-review-requirement.md)；
> 决策记录与未完成批次见 [paper-trading-plan.md](../plan/paper-trading-plan.md)。

## 1. 定位与边界

模拟交易分两层，共用一套本地落库：

1. **平台层**：每用户配置自有掘金仿真账户，页内查询资金/持仓/委托/净值，并可人工下单与撤单。
2. **交易 Agent 层**：系统级单例 Agent（非多租户）模拟一名交易员——盘后复盘解读选股 →
   制定次日交易计划 → 盘中自主执行 → 盘后分层复盘 → 经验沉淀进自有记忆反哺次日计划。

硬边界：

- **人机分账户**：人工与 Agent 用各自独立的仿真账户，净值曲线可对比、归因互不污染；
  Agent 账户由后台指定且全平台唯一，人工下单/撤单对其返回 403。
- **只模拟不实盘**：风控纪律层为将来实盘演练而建，本期仅作用于仿真柜台。
- **交易状态以柜台为准，分析与执行以本地表为准**：实时查询透传 sidecar，计划执行与
  历史复盘一律读本地表，避免盘中依赖外部服务可用性。
- **Agent 不改写其他技能域**：每日复盘、个股复盘、涨停归因只读消费，产物（计划/选股/
  复盘/记忆）落自有域。
- 不做实时推送（不用 MQTT/WebSocket），统一轮询；不做复杂策略引擎与人工条件单。

## 2. 部署拓扑

```
掘金仿真柜台 (REST)
        ▲  token / account_id 每请求头传递
        │
paper-trade sidecar (:8020，无状态代理，不持有凭证)
        ▲
        │ httpx + 风控硬校验 + 凭证解析（paper_trade_account，token Fernet 加密）
        │
┌───────┴───────────────────────────────┬───────────────────────────────┬─────────────────────┐
│ 模拟交易页（按账户）                     │ 交易 Agent 页（admin-only）      │ 盘中快反应执行           │
│ 账户选择器 / 资金 / 持仓 / 委托 / 净值   │ 对话 / 计划 / 执行动态 / 复盘 /   │ agent-intraday-exec      │
│ 人工下单与撤单（manual 账户）            │ 记忆 / 配置（模型·风控·总闸）     │ 交易时段 60s tick 循环    │
└────────────────────────────────────────┴───────────────────────────────┴─────────────────────┘
                                   │
              Celery heavy 定时链（北京时间，见 §10）
```

- **paper-trade sidecar**：`docker/paper-trade/`，compose 服务 `paper-trade:8020`。
  鉴权 token 与 account_id 由调用方按请求携带，服务本身无状态、不落凭证。
- **agent-intraday-exec**：驻留 asyncio 进程（`COLLECTOR_MODE=intraday`），交易时段内按
  `AGENT_INTRADAY_TICK_SECONDS`（默认 60s）循环；心跳写
  `collector:stream:intraday_exec:heartbeat`（TTL 120s），compose healthcheck 判活。
- **本地存储**：PostgreSQL 落交易/计划/复盘/记忆；Redis 提供分布式锁与心跳。

## 3. 数据模型

| 表 | 归属与职责 | 幂等/唯一键 |
|---|---|---|
| `paper_trade_account` | 用户账户配置（`user_id`、名称、Fernet token、`counter_account_id`、`agent_key`、启用与同步状态） | `counter_account_id` 全平台唯一；`agent_key` 部分唯一索引（全局唯一 Agent 账户） |
| `paper_trade_order` | 委托（柜台状态原值、`order_source=manual/agent`、`raw` JSONB 安全网） | `(account_id, cl_ord_id)` |
| `paper_trade_execution` | 成交回报（成交价/量/金额/佣金、回报类型原值） | `(account_id, exec_id)` |
| `paper_trade_cash_snapshot` | 资金日快照（净值/可用/余额/出入金），净值曲线与当日盈亏唯一来源 | `(account_id, trade_date)` |
| `paper_trade_position_snapshot` | 每日持仓快照（量/成本/市值/盈亏/权重），长周期复盘归因数据源 | `(account_id, trade_date, stock_code)` |
| `paper_trade_exec_observation` | 盘中逐 tick 判断留痕（盘面快照、L0 判定、L1 原始答案、动作/抑制原因、`is_shadow`） | 追加写入 |
| `trading_agent` | Agent 注册表：人设 prompt、模型绑定、方法论知识源、风控参数、盘中执行与校准三态 | `agent_key` 主键 |
| `agent_trade_plan` / `agent_trade_plan_amendment` | 交易计划与校准修正单（版本化） | 计划 `id`；修正单关联计划 |
| `agent_stock_selection` | Agent 选股清单与依据 | — |
| `agent_memory` | Agent 私有经验（discipline/method/lesson，active/archived） | `(source_result_id, title)` |

`trading_agent` 关键列：`llm_config_id`（对话/结构化模型）、`methodology_source_id`
（KB 方法论知识源）、`risk_max_position_pct` / `risk_max_total_pct` /
`risk_max_daily_orders`（风控硬校验参数，DB 真相源）、`intraday_exec_mode`
（`off/shadow/active`）、`intraday_paused`、`calibration_mode`（`off/shadow/active`）。

## 4. 服务与 API

- **服务层** `app/services/trading/`：账户、柜台客户端（httpx 封装）、风控硬校验、
  盘后同步、持仓重放、委托/成交/资金读写、计划生成与校准、执行编排、复盘
  （窗口/指标/关键交易/分区/经验）、记忆、运行留痕。
- **模拟交易 API**（JWT，按账户）：`GET/POST/PUT/DELETE /api/v1/paper-trade/accounts`、
  `GET /overview | /orders | /executions | /nav | /trade-markers`、
  `POST /orders`、`DELETE /orders/{cl_ord_id}`、`POST /accounts/{id}/sync`。
- **交易 Agent API**（admin-only）：`/api/v1/admin/trading-agent/{agent_key}/...` 覆盖
  配置、提示词、技能文件、日期轴、计划、选股、复盘（读/生成/对比）、执行动态、
  记忆（增改停用）。
- **后台账户管理**：`/api/v1/admin/paper-trade/accounts`（全平台账户视图、指定/解除
  Agent 账户、启停）。

## 5. 人工交易

- 仅限自有非 Agent 账户；限价/市价 × 买/卖，未完结委托可撤单，不做改单（撤单重下替代）。
- 行情驱动下单卡：实时行情条、现价代入、最大可买可卖、涨跌停参考与越界校验、
  确认弹窗；委托状态由延迟补同步 + 交易时段轮询自动推进；账户健康（token 失效、
  同步错误）页内可见。

## 6. 交易 Agent 会话

- 独立运行时 `agent/runtime/trading_agent.py`，复用线程/运行/SSE 基建，按
  `agent_key` 隔离会话、人设、工具与记忆；实例缓存指纹含 prompt、人设、LLM 出口、
  `TOOLS_VERSION` 与方法论源。
- 工具集见 [04-ai-agent.md](./04-ai-agent.md) §6.3；写操作前经 `ask_user` 确认。
- 前端独立页 `/trading-agent`（admin-only）；对非管理员唯一可见面是自选页 Agent 分组
  （`owner_type='agent'`，可移出不可加入）。

## 7. 盘中自主执行（快反应）

常驻服务每 tick 对全部 active 计划执行四层栈：

- **L0 确定性代码（模型不参与）**：风控硬校验（单票/总仓/单日笔数/禁 ST/T+1/
  100 股整数倍/科创板 200 股起）；精度价格穿越判定（现价 vs 买点上限/目标价/止损）；
  交易时段、涨跌停、停牌判定与计划状态机推进。不过则不动作并留痕。
- **L1 判断模型**：L0 判定进入触发区间后，一次 `ask` 并行评估全部触达计划
  （Choice 执行/等待/放弃、Noul 形态支持度、Score 盘面支持度）；按动作代价分档
  置信门控（观察类 0.6 / 资金动作 0.85 起），版本 pin 落库。
- **L2 升级**：低置信不动作、留痕，作为盘中校准与盘后复盘的输入。
- **L3 人工**：执行动态页可见（影子判断单独标识）；干预手段为移出自选 / 取消计划 /
  `intraday_paused` 暂停开关。

执行三态由 `trading_agent.intraday_exec_mode` 控制：`off` 停用、`shadow` 全链路判断
但不下单、`active` 真实下单。下单走
`agent_trade_service.place(context='scheduled', plan_id=...)`，计划转 `triggered` 并记
`triggered_cl_ord_id`；委托终态由每 tick 的未结对账回填（有未结委托即触发单账户
即时同步）：已成交（已成/部撤）→ `executed`，撤单/拒单未成交 → `failed`——静默 tick
同样对账，16:00 盘后全量同步仍是权威对账。**14:50-15:00 尾盘强检**：
所有持仓对止损线纯 L0 复检，当日未触发计划置 `expired`。

## 8. 盘中计划校准（慢思考介入）

- 时点：10:20 与 13:20 各一次（Celery heavy，`agent_plan_calib_1020` /
  `agent_plan_calib_1320`，仅交易日），避开午休与尾盘强检窗口。
- 双向契约：快反应供**盘中观察报告**（observation 当日聚合：执行概率轨迹、形态标注、
  异常事件、已执行/被抑制动作）；慢模型出**计划修正单**（`maintain/adjust/cancel/add`，
  结构化 schema 校验，落库为新计划版本）。
- 修正单必须再过 L0 风控硬校验；执行时段内只修**生效计划集**（各 Agent `plan_date`
  ≤ 当日的最近一份——计划 T-1 盘后生成、T 日盘中消费，与 tick 消费口径一致；`add`
  新建计划落回该计划集日期）；校准任务不缓存。快反应按
  计划版本号感知变更，无推送依赖。校准动作参与盘后复盘的 verdict 归因。

## 9. 判断模型接入层

- 内部契约 `app/core/decision_model`：三题型 pydantic 模型 + `ask(state, questions)`
  → 按键控答案（概率、confidence、`model_version`、usage、latency）。
- adapter 隔离厂商：SystemOne 形状首发（TypeSafe 直连 / OpenRouter 生产 Jev），
  其他端点按同形状换 base_url 即用；未来厂商 = 新 adapter。
- 配置接入「模型配置」admin（`llm_config` purpose=`decision`），DB 真相源、无新增 env；
  门控阈值按 `model_version` 键控（不同厂商 confidence 口径不可移植）。
- **降级语义**：判断模型不可用/超时不是故障——tick 照常，L1 跳过并记录降级原因；
  禁止用阈值近似替代判断。L1 题面是代码内常量契约，不进 YAML 提示词体系。

## 10. 定时编排（北京时间）

| 时刻 | 任务 | 说明 |
|---|---|---|
| T-1 19:30 | `agent-daily-plan` | 读复盘解读/结构化归因/active 记忆产出选股与次日计划，选股同步进 Agent 自选分组 |
| T 盘中 | `agent-intraday-exec` | 60s tick 快反应执行（§7） |
| T 10:20 / 13:20 | `agent-plan-calibration` | 盘中计划校准（§8） |
| T 16:00 | `paper-trade-sync` | 全启用账户委托/成交/资金/持仓快照幂等 upsert |
| T 19:00 | `paper-trade-review` | 日/周/月/季/半年/年分层复盘（六档契约见需求 09），周/月等同任务内日历判定加发 |

复盘 `experiences` 自动写入 `agent_memory`（`source='auto'`，按 `(source_result_id,title)`
去重）；active 记忆在 `agent-daily-plan` 输入中注入并随 prompt 版本纳入缓存指纹。

## 11. 部署与运维纪律

- **迁移先行**：新增表/列先 `bash docker/database/migrate.sh`，再滚动应用；对热表
  `ALTER TABLE` 后重启 worker（asyncpg 语句缓存失效）。
- **凭证**：`PAPER_TRADE_URL` 保留为部署拓扑 env；`GMTRADE_TOKEN` / `GMTRADE_ACCOUNT_ID`
  已退役；账户 token 加密依赖 `credential_encryption_key`。
- **风控参数**：DB 真相源（`trading_agent`），不走 env；admin 配置即时生效。
- **判断模型**：`llm_config` purpose=`decision`，常驻服务与 worker 均需可读。
- **验收门槛**：backend `pytest -m unit` / `mypy app/` / `ruff check .`；前端
  `typecheck` / `lint` / `test:unit` / `build`。
