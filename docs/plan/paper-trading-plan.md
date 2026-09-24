# 交易 Agent 闭环（模拟盘）实现方案

> 状态：决策点已全部拍板（§13），按批次实施，每批次独立可验收、独立提交。
> sidecar 接入事实与冒烟结论见 `docker/paper-trade/main.py` 头注释。

## 1. 背景与现状

- 已交付：`paper-trade` sidecar（compose 服务，`:8020`）接掘金线上仿真 REST 柜台，
  鉴权用仿真页 token 作 Bearer，柜台地址经 discovery 服务发现。真实冒烟已通过。
- 本方案覆盖两层：
  - **平台层（批次 1-4）**：本地落库、只读展示、Agent 交易工具、盘后同步、日/周/月复盘。
  - **自主闭环（批次 5-7）**：Agent 从每日复盘选股入自选分组 → 生成交易计划 →
    盘中定时自主执行 → 复盘分层归因 → 经验沉淀进 Agent 自有记忆反哺选股，形成完整闭环。
- 定版工作流（用户 2026-09-24 确认）：
  1. Agent 依据系统已有的每日复盘解读选股，形成 agent 自选分组（用户可见可干预）；
  2. 对自选股制定交易计划（策略 / 买卖点 / 止损点）；
  3. 交易日按定时拉起策略执行计划（非每日必有交易）；
  4. 调用工具模拟盘交易，交易记录落库，前端可查看；
  5. 每日复盘自己的交易，每周/每月复盘交易过程，页面可查看；
  6. 复盘内容经人查看/干预后沉淀进 Agent 自有记忆系统，反哺选股与计划。

## 2. 目标与非目标

**目标**

1. 委托 / 成交 / 资金快照盘后落库，成为模拟盘数据的本地真相源。
2. 前端模拟盘页：资金总览、持仓、当日委托/成交、净值曲线。
3. 助手对话可下单 / 撤单 / 查账户（写操作前 `ask_user` 确认）。
4. 盘后 LLM 日/周/月复盘：分层归因（选股 / 计划 / 执行三层对错）。
5. **Agent 选股**：盘后 LLM 任务读复盘解读 + 结构化归因 + Agent 记忆，产出选股清单
   （含依据）同步进 agent 自选分组。
6. **交易计划**：每股生成结构化计划（策略 / 买点区间 / 目标价 / 止损 / 仓位），
   全自主生效（生成即执行资格），执行后事后通知。
7. **盘中自主执行**：5 分钟条件轮询 + 尾盘强检，风控硬校验后自主下单。
8. **经验沉淀**：复盘自动提取经验直接写入 Agent 自有记忆（不经 KB 审核流）+
   手动一键沉淀；active 记忆反哺选股计划 prompt，闭环闭合。

**非目标**

- 不做多账户 / 多用户模拟盘（平台级单仿真账户，表结构预留演进不做预设计）。
- 不对接实盘（风控纪律层为将来实盘演练而建，本期仅作用于模拟盘）。
- 不做实时行情推送（MQTT/WebSocket），统一轮询。
- 不做复杂策略引擎（网格 / 定投 / 再平衡）；首期为「条件触发式」计划执行。
- 不在 sidecar 上对外暴露 MCP 端点（外部 AI 客户端接入暂缓）。

## 3. 总体架构与数据流

```
掘金仿真柜台(REST) ←── paper-trade sidecar(已交付) ←── app/services/trading（httpx 封装 + 风控硬校验）
                                                            │
         ┌──────────────────────┬───────────────────────────┤
         │                      │                           │
  盘中/实时（透传，不落库）   盘中执行（batch, */5 轮询）    盘后同步（internal, 16:00）
  助手查账户 / 模拟盘页        agent-trade-exec：            当日委托/成交/资金快照
                              读 active 计划 → 现价判定     幂等 upsert 三表
                              → 风控校验 → 下单 → 推进计划
         │                      │                           │
         └──────────┬───────────┴─────────────┬─────────────┘
                    │    盘后 heavy LLM 链（北京时序）        │
  既有复盘解读(六分区) + 涨停/异动归因 → agent-daily-plan（17:00：选股+计划+分组同步）
  本地三表交易记录（16:00 同步）        → paper-trade-review（16:10：日/周/月分层复盘）
  复盘 experiences 自动提取 → Agent 记忆库 →（人工可停用）→ 反哺 agent-daily-plan 输入（批次 7 闭合）
```

分工原则：**柜台是交易状态真相源，本地表是复盘分析与计划执行的真相源**。实时查询
透传 sidecar；计划执行与历史分析一律走本地表，避免盘中依赖外部服务可用性。

## 4. 批次 1：数据底座与盘后同步

### 4.1 迁移 `docker/database/migrations/20260924a_paper_trade_tables.sql`

新业务域启用 `paper_trade_` 前缀（对齐 `<分类前缀>_<数据类型>` 约定），三表均幂等
`CREATE TABLE IF NOT EXISTS`，同步进 `init-scripts`。

```sql
-- 委托表：幂等键 = 柜台客户端委托号
CREATE TABLE IF NOT EXISTS paper_trade_order (
    id                   BIGSERIAL PRIMARY KEY,
    cl_ord_id            VARCHAR(64)  NOT NULL,      -- 柜台 cl_ord_id（幂等键）
    trade_date           DATE         NOT NULL,      -- 业务日（柜台时间的 CN 日期）
    symbol               VARCHAR(32)  NOT NULL,      -- 掘金格式 SHSE.600000
    stock_code           VARCHAR(10)  NOT NULL,      -- 6 位代码（关联自家行情）
    side                 SMALLINT     NOT NULL,      -- 1 买 / 2 卖
    order_type           SMALLINT     NOT NULL,      -- 1 限价 / 2 市价
    position_effect      SMALLINT     NOT NULL DEFAULT 1,
    price                NUMERIC(12,4) NOT NULL DEFAULT 0,
    volume               INT          NOT NULL,
    status               SMALLINT     NOT NULL,      -- 柜台状态原值
    ord_rej_reason       SMALLINT,
    ord_rej_reason_detail TEXT,
    counter_created_at   TIMESTAMPTZ,
    counter_updated_at   TIMESTAMPTZ,
    raw                  JSONB,                      -- 柜台原始委托（字段演进安全网）
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_paper_trade_order_cl_ord_id UNIQUE (cl_ord_id)
);
CREATE INDEX IF NOT EXISTS idx_paper_trade_order_date ON paper_trade_order(trade_date DESC);

-- 成交回报表：幂等键 = 柜台回报唯一标识（实现时以回报实际字段为准，暂定 ex_exec_id）
CREATE TABLE IF NOT EXISTS paper_trade_execution (
    id                   BIGSERIAL PRIMARY KEY,
    exec_id              VARCHAR(64)  NOT NULL,      -- 柜台回报 ID（幂等键）
    cl_ord_id            VARCHAR(64)  NOT NULL,
    trade_date           DATE         NOT NULL,
    symbol               VARCHAR(32)  NOT NULL,
    side                 SMALLINT,
    exec_type            SMALLINT,                   -- 成交/撤单等回报类型
    price                NUMERIC(12,4),
    volume               INT,
    turnover             NUMERIC(18,2),              -- 成交金额
    commission           NUMERIC(12,4),
    raw                  JSONB,
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_paper_trade_execution_exec_id UNIQUE (exec_id)
);
CREATE INDEX IF NOT EXISTS idx_paper_trade_execution_date ON paper_trade_execution(trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_paper_trade_execution_cl_ord_id ON paper_trade_execution(cl_ord_id);

-- 资金日快照表：一日一行，净值曲线与当日盈亏（nav 差 + 出入金修正）的唯一来源
CREATE TABLE IF NOT EXISTS paper_trade_cash_snapshot (
    id                   BIGSERIAL PRIMARY KEY,
    trade_date           DATE         NOT NULL,
    nav                  NUMERIC(18,2),
    available            NUMERIC(18,2),
    balance              NUMERIC(18,2),
    cum_inout            NUMERIC(18,2),
    last_inout           NUMERIC(18,2),
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_paper_trade_cash_snapshot_date UNIQUE (trade_date)
);
```

要点：
- 金额 wire 层一律 float（Decimal 序列化隐患约定），DB 层 NUMERIC。
- `raw JSONB` 兜底柜台字段演进，回报字段以实抓为准后可回填。
- 委托状态中文文案映射放共享层常量（`shared/constants`），后端 wire 只透传原值。

### 4.2 模型 `backend/app/models/paper_trade.py`

域内单文件（同 `market_anomaly.py` 先例）：`PaperTradeOrder` / `PaperTradeExecution` /
`PaperTradeCashSnapshot`，`DateTime(timezone=True)` + `app.core.clock.utc_now`，
登记 `app/models/__init__.py`。

### 4.3 配置 `backend/app/core/config.py`

```python
# 掘金仿真 sidecar（compose 服务名直连；留空 = 模拟盘功能整体禁用）
paper_trade_url: str = ""
```

同步 `.env.example` 已有 `PAPER_TRADE_URL=http://paper-trade:8020`，无需新增条目。

### 4.4 服务层 `app/services/trading/`（新子域包）

- `errors.py`：`PaperTradeNotConfiguredError`（映射 503）/
  `PaperTradeGatewayError`（映射 502，携带柜台报错原文）。
- `client.py`：`PaperTradeClient`——httpx AsyncClient 薄封装（`get_cash` /
  `get_positions` / `get_intraday_orders` / `get_unfinished_orders` /
  `get_intraday_executions` / `place_order` / `cancel_order` / `cancel_all`），
  超时走 config 部署可调参数；不落库、不持状态。
- `paper_trade_service.py`：
  - `sync_daily(trade_date)`：拉 intraday 委托 + 成交 + 当日资金 → 按 `trade_date`
    推导（柜台时间转 CN 日历日）→ 幂等 upsert 三表；入口
    `redis_lock("paper-trade-sync")` 防并发；写操作显式 commit。
  - `get_orders(trade_date)` / `get_executions(trade_date)` / `get_nav_history(days)`：
    本地表查询，供 API 层。
- 依赖方向：只依赖 sidecar HTTP 与 models，禁止导入 agent/skills/runtime。

### 4.5 盘后同步任务（collector）

- `backend/collector/spiders/paper_trade_sync.py`：internal 渠道
  `BaseCollector`（同 `limit_up_ai_review.py` 先例——`collect` 占位、`run` 委托
  service），非交易日返回 `SKIPPED`（原因写 `message`）。
- `backend/collector/runtime/specs/trading.py`（新声明模块）：
  ```python
  TaskSpec(
      name="paper-trade-sync",
      label="模拟盘委托成交同步",
      data_type="paper-trade-sync",
      collectors={"internal": "collector.spiders.paper_trade_sync:PaperTradeSyncCollector"},
      queue="batch",
      description="盘后拉取掘金仿真当日委托/成交/资金快照，幂等落库",
  )
  ```
  聚合进 `specs/__init__.py` 的 `ALL_SPECS`。
- seed（`03-seed.sql` + 同步迁移）：`('paper_trade_sync_1600', 'paper-trade-sync',
  'internal', '0 16 * * 1-5', true)`——北京时间，16:00 清算稳定且在 16:10 复盘链之前，
  失败退避窗口充足。

**验收**：本地栈 `celery beat + worker` 手动触发 `paper-trade-sync`，三表落库正确；
重复执行零重复行（幂等）；非交易日 SKIPPED。

## 5. 批次 2：API 与前端只读展示

### 5.1 后端

- `backend/app/schemas/paper_trade.py`（CamelModel，金额 float）：
  `PaperTradeOverviewResponse`（cash + positions + unfinishedOrders）、
  `PaperTradeOrderRow` / `PaperTradeExecutionRow`、`NavPointResponse` +
  `PaginatedResponse` 复用。
- `backend/app/api/v1/paper_trade.py`（薄路由，注册进 v1 路由表）：
  | 端点 | 数据源 | 说明 |
  |---|---|---|
  | `GET /paper-trade/overview` | sidecar 实时透传 | 未配置时返回 `{enabled:false}` 而非 503，前端展示引导卡 |
  | `GET /paper-trade/orders?trade_date=` | 本地表 | 分页 |
  | `GET /paper-trade/executions?trade_date=` | 本地表 | 分页 |
  | `GET /paper-trade/nav?days=30` | 快照表 | 净值曲线 |
  - query 参数 snake_case（FastAPI 签名约定），日期默认 `latest_trading_day()`。
- 服务层补查询函数；路由禁止触库。

### 5.2 前端

- `shared/types/paperTrade.ts`：上述 wire 类型 + `PAGE_EVENT_TYPES.paperTrading`（批次 3 事件消费先占位）。
- `web/src/pages/PaperTrade/`（路由 `/paper-trade`，`router.tsx` + 菜单登记）：
  - `PaperTradeOverview.tsx`：资金卡（总资产 / 可用 / 当日盈亏=nav 差修正出入金）；
  - `PaperTradePositions.tsx`：持仓表（成本 / 现价 / 浮盈）；
  - `PaperTradeOrderHistory.tsx`：当日及历史委托/成交 Tab（含拒单原因红字，状态
    中文映射走 shared 常量）；
  - `NavChart.tsx`：ECharts 净值曲线。
  - 组件族保持小文件；涨跌色走 `useColorScheme()` helpers（红涨绿跌约定）。

**验收**：页面四区块出数；sidecar 未配置时展示引导卡不报错；类型检查 / 单测绿。

## 6. 批次 3：Agent 交易工具与 Skill（写路径）

### 6.1 工具 `backend/app/agent/tools/trading_tools.py`

| 工具 | 性质 | 说明 |
|---|---|---|
| `get_paper_trade_account()` | 读 | 资金 + 持仓 + 未结委托（透传 service） |
| `place_paper_trade_order(symbol, side, volume, price, order_type)` | 写 | 校验 A 股 100 股整数倍；返回柜台委托对象（含 cl_ord_id）；拒单透传 `ord_rej_reason_detail` |
| `cancel_paper_trade_order(cl_ord_id)` | 写 | 撤单 |

- 三个工具注册进 `build_assistant_tools()`。
- **工具保持薄，服务层承载逻辑**：工具层是「对话路径」与「批次 6 定时执行路径」
  共用的下单出口——风控硬校验（批次 6 定义）内聚在服务层下单函数，两条路径天然同规。
- 对话路径的确认编排放 Skill：写操作前 `ask_user` 由 SKILL.md 流程强制。
- 下单 / 撤单成功后返回值携带
  `page_event("paper_trading.complete", action=..., cl_ord_id=..., symbol=...)`。

### 6.2 回写与订阅

- `pageEvents.ts` 登记表加一条：`actionLabel: '查看模拟盘'`，`path: '/paper-trade'`；
  `stores/assistant.ts` 的 `PageAssistantResult` 联合类型加分支。
- 模拟盘页 `usePageAssistantResult('paper_trading.complete')` 订阅 → 刷新 overview +
  `message.success`。

### 6.3 `skills/paper-trading/SKILL.md`

frontmatter：`allowed-tools: get_paper_trade_account, place_paper_trade_order,
cancel_paper_trade_order, get_stock_quote, ask_user`。

流程要点（写入 SKILL.md 规则节）：
1. 下单前必调 `get_stock_quote` 取现价；限价单价格偏离现价超过 ±3% 时在确认卡中
   显式提示（仅提示不阻断）。
2. **任何写操作前必须 `ask_user`**：问题卡列明 标的 / 方向 / 数量 / 价格 / 类型 /
   预估金额，默认选项为「确认下单」。
3. 拒单时向用户转述柜台原文（如涨跌停范围校验失败）。
4. 数量必须为 100 股整数倍；科创板 200 股起、以 1 股递增（工具层校验，Skill 转述）。

**验收**：对话「以现价买 100 股浦发银行」→ 弹确认卡 → 确认后真实委托出现在模拟盘页
与柜台；撤单同链路；事件回写刷新页面。

## 7. 批次 4：模拟盘复盘（日/周/月，LLM，分层归因）

- 复盘周期 `period: day | week | month`（日度为主，周/月汇总）：
  - 输入窗口按周期取本地表区间（day = 当日；week = 本周一至今；month = 本月至今），
    资金曲线取 `paper_trade_cash_snapshot` 同区间，委托/成交按 `trade_date` 过滤。
  - 输出 Schema（结构化输出字段禁默认值约定；period 进输入自然区分 input_hash 缓存键）：
    ```
    {period, overall,
     trades: [{cl_ord_id,
               selection_verdict,   # 选股对错：对/错/中性（这只票该不该进自选）
               plan_verdict,        # 计划对错：买卖点/止损/仓位设得对不对
               execution_verdict,   # 执行对错：是否按计划执行、时机如何
               reason}],
     bias,        # 操作偏差
     suggestion,  # 改进建议
     experiences: [{title, body, mem_type}]}    # 批次 7 消费：经验提取（discipline|method|lesson）
    ```
    分层归因是批次 7 记忆沉淀精准反哺的前提（选股错→沉淀选股纪律；计划错→沉淀
    计划方法；执行错→沉淀执行纪律），一次 LLM 输出全部字段，不做二次调用。
- 定时：`paper_trade_review_1610`（heavy 队列，串行在 sync 之后；input_hash 缓存 +
  redis 并发锁，复用 review 服务层范式）。周/月不单独建 cron——同一任务内用
  `app.core.clock` 日历判定加发：周五盘后加发周度；月末最后一个交易日盘后加发月度
  （cron 表达不了"最后交易日"，任务内判定 + SKIP 复用既有机制）。
- 落库：复用 `ai_analysis_result`（`skill_id='paper-trade-review'`），不建新表；
  页面在模拟盘页内嵌「AI 复盘」卡片 + page_event。

**验收**：盘后自动生成复盘（分层 verdict 齐全）；同日重跑命中缓存；页面卡片展示；
周五/月末自动加发对应周期。

## 8. 批次 5：Agent 选股与交易计划（闭环第一步）

### 8.1 数据底座

迁移 `20260924b_agent_trading_tables.sql`（幂等，同步 init-scripts）：

```sql
-- agent 自选分组归属：现有分组表加归属标记（迁移，非新表）
ALTER TABLE user_watchlist_group ADD COLUMN IF NOT EXISTS owner_type VARCHAR(16) NOT NULL DEFAULT 'user';
-- owner_type = 'agent' 的分组即「交易 Agent」分组（平台级唯一，服务层保证单例）

-- 选股记录：选股依据真相源（复盘「选股对错」归因输入；人工移出干预记录）
CREATE TABLE IF NOT EXISTS agent_stock_selection (
    id                   BIGSERIAL PRIMARY KEY,
    trade_date           DATE         NOT NULL,      -- 选入日
    stock_code           VARCHAR(10)  NOT NULL,
    reason               TEXT         NOT NULL,      -- 选股依据（引用复盘结论）
    source_result_id     BIGINT,                     -- ai_analysis_result.id（复盘解读）
    confidence           NUMERIC(5,4),               -- LLM 置信度（可空）
    status               VARCHAR(16)  NOT NULL DEFAULT 'active',   -- active / removed
    removed_at           TIMESTAMPTZ,
    removed_reason       TEXT,                       -- agent 剔除 / manual 人工移出
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agent_stock_selection_date_code UNIQUE (trade_date, stock_code)
);
CREATE INDEX IF NOT EXISTS idx_agent_stock_selection_code ON agent_stock_selection(stock_code, trade_date DESC);

-- 交易计划：盘中执行的真相源（每日盘后生成，条件触发式）
CREATE TABLE IF NOT EXISTS agent_trade_plan (
    id                   BIGSERIAL PRIMARY KEY,
    plan_date            DATE         NOT NULL,      -- 计划日（默认当日有效）
    stock_code           VARCHAR(10)  NOT NULL,
    plan_type            VARCHAR(8)   NOT NULL,      -- buy 开仓 / sell 持仓管理
    strategy             TEXT         NOT NULL,      -- 策略描述
    buy_zone_low         NUMERIC(12,4),              -- 买点区间（buy 必填）
    buy_zone_high        NUMERIC(12,4),
    target_price         NUMERIC(12,4),              -- 止盈目标价（sell 必填）
    stop_loss            NUMERIC(12,4) NOT NULL,     -- 止损价（两类计划均必填，纪律）
    position_pct         NUMERIC(5,2)  NOT NULL,     -- 目标仓位（占总资产 %）
    status               VARCHAR(16)   NOT NULL DEFAULT 'active',
    -- 状态机：active → triggered（已触发下单）→ executed / expired（当日未触发）/ cancelled（人工取消）
    selection_id         BIGINT,                     -- 依据 agent_stock_selection（sell 计划可空）
    basis                TEXT         NOT NULL,      -- 计划依据（复盘结论/经验卡片引用）
    triggered_cl_ord_id  VARCHAR(64),                -- 触发的委托（关联 paper_trade_order）
    triggered_at         TIMESTAMPTZ,
    raw                  JSONB,                      -- LLM 完整输出兜底
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agent_trade_plan_date_code_type UNIQUE (plan_date, stock_code, plan_type)
);
CREATE INDEX IF NOT EXISTS idx_agent_trade_plan_status ON agent_trade_plan(status, plan_date DESC);
```

### 8.2 生成任务 `agent-daily-plan`（heavy 队列）

- seed：`('agent_daily_plan_1700', 'agent-daily-plan', 'internal', '0 17 * * 1-5', true)`
  ——北京 17:00，串行在 16:00 sync / 16:10 复盘 / 16:30 涨停归因之后；输入未就绪走
  `ReviewInputDataNotReadyError` 退避重试。
- spider：`backend/collector/spiders/agent_daily_plan.py`（internal，同先例）；TaskSpec
  追加进 `runtime/specs/trading.py`。
- 服务层 `app/services/trading/agent_plan_service.py`：
  1. **输入组装**：当日复盘解读全文（`ai_analysis_result`：market-daily-review）+
     涨停归因 groups/stock_codes + 异动归因 top-N + 当前模拟盘持仓（本地表）+
     **人工移出历史**（`agent_stock_selection.removed_reason='manual'` 近期清单，
     prompt 显式声明避免重复选入）+ Agent 记忆检索（`agent_memory` 中 `status='active'`
     条目，按相关性与新近度注入并做 token 上限截断；批次 7 之前该输入自然为空集，
     链路先行不阻塞）。
  2. **LLM 结构化输出**（`run_structured`，字段禁默认值）：
     `{selections: [{stock_code, reason, confidence}],
       plans: [{stock_code, plan_type, strategy, buy_zone_low/high, target_price,
                stop_loss, position_pct, basis}]}`——买卖点以当日收盘价为基准；
     每个持仓标的必须产出 sell 计划（含 stop_loss，执行纪律）。
  3. **落库与分组同步**：upsert `agent_stock_selection`（当日清单）+
     `agent_trade_plan`（全自主：生成即 `active` 生效）；agent 分组同步
     （选入加入 / 未续选且过期移出标 `removed`，人工移出不覆盖）。
  4. `redis_lock` + input_hash 缓存复用 review 范式；`paper_trade_url` 未配置整体
     SKIPPED。

### 8.3 前端（自选页内 Agent 分组）

- `Watchlist/index.tsx` 渲染 `owner_type='agent'` 分组：AI 徽标 + 选股依据
  （reason 摘要，展开看全文）+ 置信度；用户可移出（标 `removed_reason='manual'`），
  不可手动加入。
- 模拟盘页加「今日交易计划」区块：计划列表（方向 / 买点区间 / 止盈 / 止损 /
  仓位 / 状态 / 依据），当日计划可人工 `cancelled`（干预手段之一）。

**验收**：盘后 17:00 自动产出选股清单 + 计划；agent 分组与依据可见；人工移出后
次日不重复选入；重跑命中缓存；非交易日 SKIPPED。

## 9. 批次 6：盘中自主执行（闭环第二步）

### 9.1 执行任务 `agent-trade-exec`（batch 队列）

- seed：`('agent_trade_exec_5min', 'agent-trade-exec', 'internal', '*/5 9-14 * * 1-5',
  true)`——beat 每 5 分钟派发，**任务内判定交易时段**（9:30-11:30 / 13:00-15:00，
  `app.core.clock`，非时段 SKIPPED）；14:50 后进入「尾盘强检」模式（同一任务内分模式，
  避免双任务并发互斥）。`redis_lock` 防重入；非交易日 SKIPPED。
- 服务层 `app/services/trading/agent_exec_service.py`，单轮逻辑：
  1. 读当日 `active` 计划 → 逐计划 `get_stock_quote` 取现价；
  2. **条件判定**：buy 计划现价 ≤ `buy_zone_high` 触发买入（限价，价格 = 买点上限）；
     sell 计划现价 ≥ `target_price`（止盈）或 ≤ `stop_loss`（止损）触发卖出
     （限价，保护性偏离限幅）；
  3. **风控硬校验**（服务层内聚，与 LLM 无关，参数进 config）：
     单票市值 ≤ 总资产 20%、总持仓 ≤ 总资产 80%、禁 ST/退市风险股、单日下单 ≤ 10 笔、
     T+1（卖出标的必须是此前交易日买入——查本地 execution）、100 股整数倍、
     科创板 200 股起；任一不过则计划保持 active 并记录原因（不告警式失败）；
  4. **下单**（批次 3 服务层下单函数）→ 成功后推进计划 `triggered` + 记
     `triggered_cl_ord_id`，成交确认依赖 16:00 sync 回填；
  5. **尾盘强检**（14:50-15:00 窗口）：全部持仓对 `stop_loss` 强检一遍（含当日无
     sell 计划的持仓——按计划纪律兜底）；当日仍未触发计划标 `expired`。
- config 新增：`agent_risk_max_position_pct=20` / `agent_risk_max_total_pct=80` /
  `agent_risk_max_daily_orders=10`（env 可覆盖）。

### 9.2 事后通知与可见性

- 不新建通知系统：执行动态三处可见——
  1. 模拟盘页「今日交易计划」区块状态实时推进（triggered/executed）；
  2. 模拟盘页「Agent 执行动态」条（读 plan×order 关联：时间 / 标的 / 方向 /
     数量 / 价格 / 触发原因[止盈|止损|买点|尾盘强检]）；
  3. 工作台卡片「Agent 交易动态」（当日执行笔数 + 最新一笔，范本
     `AiReviewSection.tsx`）。

### 9.3 盘中判定引入 Jev 的可行性调研（结论：暂缓，留缝）

调研结论（2026-09-24）：**核心触发判定维持确定性代码，本期不引入 Jev；在
`agent_exec_service` 预留可替换的条件判定缝，待其成熟与中文输入验证后再评估。**

- API 形态（官方）：`POST /v1/systemone`（Bearer），body `{state, model: "jev-latest",
  questions: {id: Question}}` → `{answers: {id: Answer}, usage}`。题型 `noul`（是非 →
  P(yes)）/ `choice`（单选）/ `score`（2-10 级有序打分），均带 confidence。
  ~250ms 延迟，$0.042/M input tokens（输出免费），单请求 64k token 预算（state+最长
  问句 ≤32k），1200 req/min——延迟与成本对 5 分钟轮询完全无压力。
- **根本不匹配**：批次 6 的条件判定是「现价 vs 阈值」数值比较，而 Jev 官方明确
  不支持数学/计数/数值比较（字面读题、无数值推理），把它当比较器用是逆着产品边界走，
  答错无告警。
- **可取场景（即预留的判断缝）**：阈值附近噪声带判定（现价贴着 `buy_zone_high`
  算不算「触及买点」）、跳空/涨跌停/停牌等非常态盘面下的执行取舍、下单前护栏确认
  （「此计划在当前盘面下是否仍应执行」）——这类语义判断 if-else 写不出，Jev 的
  confidence 分档（只读 0.6 / 资金动作 0.9）机制可套用。
- **暂缓的硬理由**：
  1. 官方自述非英语输入「可用但更弱，需盯 confidence」——本方案 state 全中文盘面
     描述，置信度校准性未经验证，而资金动作恰恰要求高置信可靠；
  2. 产品早期访问阶段（别名 `jev-latest` 会漂移，阈值调好后须 pin `jev-1.13.0`
     这类具体版本），供应商单一，无余额/配额查询端点，用超限只能靠 429 被动感知；
  3. 长数组位置索引实测不可靠（150 项 27% 错位）——若批量问每只持仓的执行取舍，
     必须逐项内嵌问句或键控对象，工程上可用但多一层踩坑面；
  4. 风控纪律要求判定路径可测试、可回放、可审计，确定性代码天然满足，LLM 判定
     缝启用时须另行补校准与回放机制。
- 落地方式：条件判定实现为纯函数（输入计划 + 现价 + 盘面快照，输出 触发/不触发 +
  原因），风控硬校验与状态机不依赖其内部实现；将来启用 Jev 只替换缝内实现，
  不动批次 6 其余部分。本批次不新增任何外部依赖。

**验收**：盘中模拟一个触达买点的标的 → 5 分钟内自主下单 → 计划状态推进 → 委托
落 `paper_trade_order` → 风控约束生效（构造超仓位计划被拒）；尾盘强检与 expired
推进正确；非交易时段 SKIPPED。

## 10. 批次 7：经验沉淀闭环（复盘 → Agent 自有记忆 → 反哺）

记忆落 **Agent 自有记忆系统**（新表 `agent_memory`），不经 KB 知识库——记忆是
Agent 的私有资产，自动提取直接生效（无草稿/审核流转），人只做查看、停用与手动
补充三类干预。

### 10.1 数据底座

迁移 `20260924c_agent_memory.sql`（幂等，同步 init-scripts）：

```sql
CREATE TABLE IF NOT EXISTS agent_memory (
    id                   BIGSERIAL PRIMARY KEY,
    mem_type             VARCHAR(16)  NOT NULL,      -- discipline 纪律 / method 方法 / lesson 教训
    title                VARCHAR(128) NOT NULL,
    body                 TEXT         NOT NULL,
    source               VARCHAR(16)  NOT NULL,      -- auto 复盘自动提取 / manual 人工沉淀
    status               VARCHAR(16)  NOT NULL DEFAULT 'active',   -- active / archived（停用不删）
    source_result_id     BIGINT,                     -- ai_analysis_result.id（auto 时必填，溯源）
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agent_memory_source_title UNIQUE (source_result_id, title)
);
CREATE INDEX IF NOT EXISTS idx_agent_memory_status ON agent_memory(status, mem_type);
```

不预设计量/检索列：记忆量级为每日几条、累计数百条，反哺按「全量 active 注入 +
token 上限截断」即可；规模到需要相关性检索时再加列演进。

### 10.2 自动提取（直接生效）

- 数据源：批次 4 复盘输出的 `experiences`（同一次 LLM 输出，无额外调用）。
- 复盘生成完成后直接写 `agent_memory`（`source='auto'`、`status='active'`）——
  分层归因决定 `mem_type`：选股错 → discipline（选股纪律）；计划错 → method
  （计划方法）；执行错 → discipline（执行纪律）；跨 trade 共性 → lesson。
- 幂等：按 `(source_result_id, title)` 去重，重跑不重复入库。

### 10.3 人工干预（查看 / 停用 / 手动沉淀）

- 模拟盘页新增「Agent 记忆」区块：记忆列表（类型 / 标题 / 正文 / 来源 / 状态），
  可 `archived` 停用（不物理删除，保留归因链路）。
- 复盘卡片每条 trade verdict 与 overall 旁加「沉淀为记忆」按钮 →
  `POST /api/v1/paper-trade/review/precipitate`（v1 用户路径，服务层直写
  `agent_memory`，`source='manual'`、`status='active'`——用户主动即生效）→
  `message.success`。前端对话框预填标题/正文（来自所选 verdict reason），可编辑后提交。

### 10.4 反哺闭合

- 批次 5 `agent-daily-plan` 的记忆检索输入（`status='active'`）在批次 7 供数后自然
  生效——**注入接线在批次 5 已完成，本批次只供数**。
- 闭环验证：复盘沉淀一条「追高风险」纪律记忆 → 次日选股/计划 prompt 引用该记忆
  （日志验证）；停用后次日不再引用。

**验收**：复盘后 experiences 自动进 `agent_memory` 且 active；停用一条记忆后次日
prompt 不再引用；手动沉淀一键 active（manual 标记）；重跑不重复入库。

## 11. 扩展（暂缓，不在本期）

- sidecar 增加 MCP streamable-http 端点，供外部 AI 客户端（如 Claude）直接交易。
- 出入金 API（`/v3/accounts/{id}/cash-inout`）与手续费设置对接。
- 多仿真账户支持（表已按平台级设计，届时加 account 维度列 + 迁移）。
- 实盘对接（复用风控纪律层 + 柜台适配器，另立方案）。
- 执行通知外扩（邮件 / webhook）；复杂策略引擎（网格 / 定投 / 再平衡）。

## 12. 部署与验收纪律

- 迁移先于代码滚动（新表无热表 DDL 风险，仍按纪律先跑迁移再换镜像；批次 5 的
  `ALTER TABLE user_watchlist_group` 后重启 worker——asyncpg 语句缓存失效纪律）。
- 生产 `.env` 追加 `GMTRADE_TOKEN` / `GMTRADE_ACCOUNT_ID`（token 视同密码）。
- 每批次完成：`uv run mypy app/` + `uv run pytest -m unit` + `uv run ruff check .`；
  前端 `npm run build` + 类型检查。

## 13. 决策点记录（已全部拍板）

| # | 决策 | 结论 |
|---|---|---|
| D1 | 盘后同步时刻 | **16:00**（清算稳定 + 退避窗口足） |
| D2 | 模拟盘页入口形态 | **独立页 `/paper-trade`** |
| D3 | 复盘产出粒度 | **日度为主 + 周度/月度汇总**——同一任务内 `app.core.clock` 日历判定加发，不单独建 cron |
| D4 | 复盘落库 | **复用 ai_analysis_result**（skill_id 区分） |
| D5 | 下单确认阈值 | **±3%，仅提示不阻断** |
| D6 | 定时执行确认模式 | **全自主 + 事后通知**——计划生成即生效，不设人工审批；执行动态经页面可见（§9.2），人工干预手段 = 移出自选 / 取消计划 |
| D7 | agent 分组形态 | **现有自选页内 Agent 分组**（`owner_type='agent'`），AI 徽标 + 依据可见，可移出不可加入 |
| D8 | 记忆沉淀语义 | **落 Agent 自有记忆（`agent_memory`），不经 KB 审核流**：自动提取直接 active + 手动沉淀 active（source 标记区分）；人工干预 = 查看 / 停用 |
| D9 | 盘中触发方式 | **5 分钟条件轮询 + 14:50 尾盘强检**（单任务内分模式） |
| D10 | 执行自主度风控 | 服务层硬校验参数化：单票 ≤20% / 总仓 ≤80% / 单日 ≤10 笔 / 禁 ST / T+1（默认值可在实施时调整） |
| D11 | 盘中判定引入 Jev | **暂缓，留缝**——数值比较超出 Jev 能力边界，核心判定维持确定性代码；`agent_exec_service` 条件判定预留纯函数缝，待中文输入验证与产品成熟后再评估（§9.3） |
