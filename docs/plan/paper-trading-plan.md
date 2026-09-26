# 交易 Agent 闭环（模拟交易）实现方案

> 状态：决策点已全部拍板（§15），按批次实施，每批次独立可验收、独立提交。
> 2026-09-24 需求扩展①：多租户账户配置、人工交易入口、后台指定 agent 账户（D12-D15）。
> 2026-09-24 需求扩展②：交易 Agent 定位定稿——系统级独立 agent、专属工具、独立页
> admin-only、记忆可编辑、配置面（D16-D19）。
> 2026-09-24 需求扩展③：人工交易体验优先（D20）——新增批次 4「人工交易体验优化」，
> Agent 闭环整体后移；批次重排为 1-9（原 3-7 顺延为 4-8，扩展③后原 4-8 顺延为 5-9）。
> sidecar 接入事实与冒烟结论见 `docker/paper-trade/main.py` 头注释。

## 1. 背景与现状

- 已交付：`paper-trade` sidecar（compose 服务，`:8020`）接掘金线上仿真 REST 柜台，
  鉴权用仿真页 token 作 Bearer，柜台地址经 discovery 服务发现。真实冒烟已通过。
- 已交付：批次 1（数据底座与盘后同步）+ 批次 2（API 与前端只读展示）。
  两批次按「平台级单账户」实现，多租户化增补由批次 3 统一演进（分支未合并，无兼容负担）。
- 本方案覆盖两层：
  - **平台层（批次 1-4）**：本地落库、只读展示、多租户账户配置与人工交易、
    人工交易体验优化（批次 4，体验优先，D20）。
  - **交易 Agent 闭环（批次 5-9）**：独立会话与专属工具 → 每日复盘选股入自选分组 →
    生成交易计划 → 盘中定时自主执行 → 复盘分层归因 → 经验沉淀进 Agent 自有记忆反哺选股，形成完整闭环。
- 定版工作流（用户 2026-09-24 确认）：
  1. Agent 依据系统已有的每日复盘解读选股，形成 agent 自选分组（用户可见可干预）；
  2. 对自选股制定交易计划（策略 / 买卖点 / 止损点）；
  3. 交易日按定时拉起策略执行计划（非每日必有交易）；
  4. 调用工具模拟交易，交易记录落库，前端可查看；
  5. 每日复盘自己的交易，每周/每月复盘交易过程，页面可查看；
  6. 复盘内容经人查看/干预后沉淀进 Agent 自有记忆系统，反哺选股与计划。
- **人机并行（D14）**：人与 Agent 各用独立仿真账户——人配置自己的账户手动交易，
  Agent 使用后台指定的专属账户自主交易，两条净值曲线可对比，归因互不污染。
- **交易 Agent 定位（D16-D18）**：系统级单例的独立 agent——模拟一名交易员，
  与侧边栏助手及每日复盘/个股复盘/涨停归因等技能域解耦：**只读取其产出数据为它所用，
  不回写这些域**，产物一律落自有域（计划/选股/复盘/记忆）。对话、工具、记忆、
  配置均独立；前端独立页承载，仅管理员可访问。

## 2. 目标与非目标

**目标**

1. 委托 / 成交 / 资金快照盘后落库，成为模拟交易数据的本地真相源。
2. 前端模拟交易页：资金总览、持仓、当日委托/成交、净值曲线。
3. **多租户账户**：每用户配置自有掘金账户（token / account_id 入库加密），
   页面按账户展示（多账户选择器），未配置时页内展示使用方法引导。
4. **人工交易入口**：页面下单卡（限价/市价 × 买/卖）+ 未完结委托撤单，
   用于验证模拟交易链路可用性（仅限自有非 agent 账户）。
5. **人工交易体验（批次 4，体验优先）**：行情驱动下单卡（实时行情条 / 现价代入 /
   最大可买可卖 / 涨跌停参考与越界校验）、下单确认弹窗、持仓联动快捷下单、
   委托状态自动推进（延迟补同步 + 交易时段轮询）、交易时段状态提示、
   账户健康透明（token 失效定向提示 / 同步错误可见）——人工模拟交易对标
   同花顺核心体验（§7）。
6. **后台管理**：管理员查看全平台账户配置，指定全局唯一的 agent 专属账户。
7. **交易 Agent（系统级单例，D16-D18）**：独立页承载——交易员人格独立对话
   （写操作前 `ask_user` 确认）、专属工具集（交易执行 / 计划 / 记忆 / 只读取数）、
   今日计划与执行动态、复盘卡片、记忆管理（可见可编辑可停用）、
   配置面（模型 / 风控参数 / 自主执行总闸）；仅管理员可访问。
8. 盘后 LLM 日/周/月复盘：分层归因（选股 / 计划 / 执行三层对错）。
9. **Agent 选股**：盘后 LLM 任务读复盘解读 + 结构化归因 + Agent 记忆，产出选股清单
   （含依据）同步进 agent 自选分组。
10. **交易计划**：每股生成结构化计划（策略 / 买点区间 / 目标价 / 止损 / 仓位），
    全自主生效（生成即执行资格），执行后事后通知。
11. **盘中自主执行**：5 分钟条件轮询 + 尾盘强检，风控硬校验后自主下单
    （总闸可关，§8.5）。
12. **经验沉淀**：复盘自动提取经验直接写入 Agent 自有记忆（不经 KB 审核流）+
    手动一键沉淀；active 记忆反哺选股计划 prompt，闭环闭合。

**非目标**

- 不做多 agent 实例 / 团队 agent（交易 Agent 全系统单例，不做多租户化）；
  非管理员不可访问交易 Agent 页（其选股经自选页 agent 分组对全员可见可移出，
  作为干预面）。
- 不做租户间账户共享 / 团队账户（每账户归属唯一用户）；不代理掘金注册
  （用户自行在 sim.myquant.cn 注册并获取 token / account_id）。
- 不对接实盘（风控纪律层为将来实盘演练而建，本期仅作用于模拟交易）。
- 不做实时行情推送（MQTT/WebSocket），统一轮询。
- 人工侧不做五档盘口行情条（平台行情源无买卖五档字段）；人工账户不做本地
  条件单/止盈止损监控单（条件触发属 agent 计划执行域，列入 §13 扩展）。
- 不做复杂策略引擎（网格 / 定投 / 再平衡）；首期为「条件触发式」计划执行。
- 不在 sidecar 上对外暴露 MCP 端点（外部 AI 客户端接入暂缓）。
- 人工交易不做改单（撤单后重新下单替代）；人工账户不做 LLM 复盘
  （复盘对象固定为 agent 账户，人工账户仅页面数据展示）。
- 交易 Agent 不修改每日复盘 / 个股复盘 / 涨停归因等既有技能域的任何数据
  （只读消费其产出）。

## 3. 总体架构与数据流

```
掘金仿真柜台(REST) ←── paper-trade sidecar(无状态代理：每请求携带 token/account_id 头)
                                                        │
              app/services/trading（httpx 封装 + 风控硬校验 + 凭证解析）
                  凭证来源：paper_trade_account 表（token Fernet 加密，
                  复用 app/utils/crypto；agent 账户 = is_agent 全局唯一行）
                                                        │
      ┌──────────────────────┬──────────────────────────┼─────────────────────────┐
      │                      │                          │                         │
 模拟交易页(按账户)      交易 Agent 页(admin-only)   盘中执行(batch, */5 轮询)   盘后同步(internal, 16:00)
 账户选择器/配置引导      独立对话(ask_user 确认)     agent-trade-exec：         循环所有启用账户
 资金/持仓/委托/净值      专属工具集(交易执行/计划/   读 active 计划 → 现价判定   当日委托/成交/资金快照
 人工下单+撤单(manual)   记忆/只读取数)             → 风控校验(读配置表)        幂等 upsert 三表
 后台管理(账户视图+      计划/执行动态/复盘/记忆     → 下单(source='agent')     (按账户隔离错误)
 agent 指定)            配置(模型/风控/自主总闸)
      │                      │                          │                         │
      └──────────────────────┴────────────┬─────────────┴─────────────────────────┘
                                           │    盘后 heavy LLM 链（北京时序）
  既有复盘解读(六分区) + 涨停/异动归因 →(只读消费) agent-daily-plan（19:00：选股+计划+分组同步）
  agent 账户本地三表交易记录（16:00 同步）→ paper-trade-review（16:10：日/周/月分层复盘）
  复盘 experiences 自动提取 → Agent 记忆库 →（人工可停用）→ 反哺 agent-daily-plan 输入（批次 9 闭合）
```

分工原则：**柜台是交易状态真相源，本地表是复盘分析与计划执行的真相源**。实时查询
透传 sidecar（按请求账户）；计划执行与历史分析一律走本地表，避免盘中依赖外部服务可用性。
页面分工：**模拟交易页 = 账户数据**（多账户资金/持仓/委托/净值 + 人工交易）；
**交易 Agent 页 = agent 大脑**（对话/计划/执行动态/复盘/记忆/配置），数据互通不重复。

## 4. 批次 1：数据底座与盘后同步（已交付；表结构由批次 3 演进加账户维度）

### 4.1 迁移 `docker/database/migrations/20260924a_paper_trade_tables.sql`

新业务域启用 `paper_trade_` 前缀（对齐 `<分类前缀>_<数据类型>` 约定），三表均幂等
`CREATE TABLE IF NOT EXISTS`，同步进 `init-scripts`。批次 3 直接在该迁移文件上演进
（分支未合并，不产生增量迁移），终态见 §6.1。

```sql
-- 委托表：幂等键 = 柜台客户端委托号（按账户唯一）
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
登记 `app/models/__init__.py`。批次 3 增加 `PaperTradeAccount`。

### 4.3 配置 `backend/app/core/config.py`

```python
# 掘金仿真 sidecar（compose 服务名直连；留空 = 模拟交易功能整体禁用）
paper_trade_url: str = ""
```

柜台凭证不入 env（D12）：token / account_id 入 `paper_trade_account` 表，
`credential_encryption_key` 沿用既有配置（proxy 密码加密同源）。

### 4.4 服务层 `app/services/trading/`（新子域包）

- `errors.py`：`PaperTradeNotConfiguredError`（映射 503）/
  `PaperTradeGatewayError`（映射 502，携带柜台报错原文）。
- `client.py`：`PaperTradeClient`——httpx AsyncClient 薄封装（`get_cash` /
  `get_positions` / `get_intraday_orders` / `get_unfinished_orders` /
  `get_intraday_executions` / `place_order` / `cancel_order` / `cancel_all`），
  超时走 config 部署可调参数；不落库、不持状态。批次 3 起方法签名携带
  每请求凭证（token + account_id）。
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
      label="模拟交易委托成交同步",
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
重复执行零重复行（幂等）；非交易日 SKIPPED。（多账户循环验收见 §6.6）

## 5. 批次 2：API 与前端只读展示（已交付；账户维度由批次 3 增补）

### 5.1 后端

- `backend/app/schemas/paper_trade.py`（CamelModel，金额 float）：
  `PaperTradeOverviewResponse`（cash + positions + unfinishedOrders）、
  `PaperTradeOrderRow` / `PaperTradeExecutionRow`、NavPointResponse +
  PaginatedResponse 复用。
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

- `shared/types/paperTrade.ts`：上述 wire 类型 + `PAGE_EVENT_TYPES.paperTrading`（批次 5 事件消费先占位）。
- `web/src/pages/PaperTrade/`（路由 `/paper-trade`，`router.tsx` + 菜单登记）：
  - `PaperTradeOverview.tsx`：资金卡（总资产 / 可用 / 当日盈亏=nav 差修正出入金）；
  - `PaperTradePositions.tsx`：持仓表（成本 / 现价 / 浮盈）；
  - `PaperTradeOrderHistory.tsx`：当日及历史委托/成交 Tab（含拒单原因红字，状态
    中文映射走 shared 常量）；
  - `NavChart.tsx`：ECharts 净值曲线。
  - 组件族保持小文件；涨跌色走 `useColorScheme()` helpers（红涨绿跌约定）。

**验收**：页面四区块出数；sidecar 未配置时展示引导卡不报错；类型检查 / 单测绿。
（多账户选择器与引导卡终态见 §6.5）

## 6. 批次 3：多租户账户配置与人工交易（本次需求扩展）

覆盖五项需求：菜单改名「模拟交易」、凭证入库配置、人工交易入口、多租户、
后台指定 agent 账户。批次 1/2 已交付物在此批次内统一演进。

### 6.1 迁移（直接演进 `20260924a_paper_trade_tables.sql`，分支未合并无增量）

```sql
-- 账户配置表：掘金仿真凭证入库（token Fernet 加密，复用 utils/crypto 与 proxy 先例）
CREATE TABLE IF NOT EXISTS paper_trade_account (
    id               BIGSERIAL PRIMARY KEY,
    user_id          INTEGER      NOT NULL,      -- 归属租户（users.id）
    name             VARCHAR(64)  NOT NULL,      -- 展示名（如「人工盘」「agent 盘」）
    token_encrypted  TEXT         NOT NULL,      -- 掘金仿真 token（Fernet）
    counter_account_id VARCHAR(64) NOT NULL,     -- 掘金仿真 account_id
    is_agent         BOOLEAN      NOT NULL DEFAULT FALSE,   -- agent 专属账户（全局唯一）
    is_enabled       BOOLEAN      NOT NULL DEFAULT TRUE,
    last_error       TEXT,                       -- 最近一次同步/调用错误（诊断）
    last_synced_at   TIMESTAMPTZ,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_paper_trade_account_counter UNIQUE (counter_account_id)
);
-- 同一柜台账户全平台仅允许配置一次（防 token 共享/多头配置）
CREATE UNIQUE INDEX IF NOT EXISTS uq_paper_trade_account_agent
    ON paper_trade_account (is_agent) WHERE is_agent;   -- agent 指定全局唯一
CREATE INDEX IF NOT EXISTS idx_paper_trade_account_user ON paper_trade_account (user_id);

-- 三张数据表加账户维度 + 委托来源标记
ALTER TABLE paper_trade_order
    ADD COLUMN IF NOT EXISTS paper_trade_account_id INTEGER,
    ADD COLUMN IF NOT EXISTS order_source VARCHAR(8) NOT NULL DEFAULT 'manual';
-- （新建表场景直接写入列定义；以上 ALTER 仅幂等兜底）
-- 唯一约束收紧为按账户：uq (paper_trade_account_id, cl_ord_id) /
--   execution: uq (paper_trade_account_id, exec_id) /
--   cash_snapshot: uq (paper_trade_account_id, trade_date)
-- 索引同步加账户前导列：(paper_trade_account_id, trade_date DESC)
```

要点：
- `order_source`：`manual`（页面人工）/ `agent`（Agent 工具与定时执行）——人机分账户
  之外再留数据层来源标记，复盘归因可过滤（D14）。
- DB 层不建 FK 约束（对齐域内现状），引用完整性由服务层保证。
- 同步 `init-scripts`；compose 移除 sidecar 的 `GMTRADE_TOKEN`/`GMTRADE_ACCOUNT_ID`。

### 6.2 sidecar 无状态化（`docker/paper-trade/main.py`）

- 凭证从 env 改为**每请求头**：`X-Gm-Token` + `X-Gm-Account-Id`，缺失返回 400；
  `GMTRADE_TOKEN` / `GMTRADE_ACCOUNT_ID` env 退役。
- discovery 服务发现与 `GMTRADE_BROKER_URL` 钉死优先逻辑不变（柜台地址与账户无关）；
  token 无效 401 映射不变（前端据此提示重置 token）。
- 端点面不变：cash / positions / orders(intraday/unfinished) / executions /
  submit / cancel。token 仅在 compose 内网传递，不出网。

### 6.3 模型与服务层

- 模型：`PaperTradeAccount` 登记进 `app/models/paper_trade.py` +
  `app/models/__init__.py`；三张数据表模型加列。
- 加密：复用 `app/utils/crypto.py`（`encrypt_token` / `decrypt_token` /
  `mask_token`，proxy 密码同源）；token 任何 wire 响应只回 `tokenMasked`。
- `account_service.py`（新）：
  - 用户侧 CRUD：每用户上限 10 个账户（模块常量）；`counter_account_id` 全局唯一
    冲突转 409；更新时 token 留空 = 不改；删除仅限无本地数据的账户
    （三表有记录则 409，只允许停用）——保护复盘链路。
  - `resolve_for_user(user_id, account_id=None)`：校验归属 + 启用，缺省取首个启用
    账户；解密 token 返回调用上下文。
  - `resolve_agent_account()`：`is_agent=true` 唯一行（批次 5 消费）；未指定抛
    `PaperTradeAgentAccountMissingError`（409 语义）。
  - 指定/取消 agent：事务内先清后设，部分唯一索引兜底并发。
- `paper_trade_service.py`：查询与同步函数全部加 `paper_trade_account_id` 维度；
  下单/撤单服务函数带 `source` 参数——**agent 账户拒收 `source='manual'`**（403 语义，
  D14）；下单成功写 `order_source`。

### 6.4 API（`backend/app/api/v1/paper_trade.py` + admin 路由）

用户侧（当前登录用户，全部走归属校验）：

| 端点 | 说明 |
|---|---|
| `GET /paper-trade/accounts` | 自有账户列表（token 只回脱敏） |
| `POST /paper-trade/accounts` | 新建 `{name, token, accountId}` |
| `PUT /paper-trade/accounts/{account_id}` | 更新（token 可选） |
| `DELETE /paper-trade/accounts/{account_id}` | 无本地数据才可删，否则 409 |
| `GET /paper-trade/overview?account_id=` | 现有端点加账户维度，缺省首个启用账户；用户未配任何账户返回 `{enabled:false}`（前端引导） |
| `GET /paper-trade/orders\|executions\|nav` | 同上加 `account_id` |
| `POST /paper-trade/orders` | 人工下单 `{accountId, symbol, side, orderType, price, volume}`；agent 账户 403 |
| `DELETE /paper-trade/orders/{cl_ord_id}?account_id=` | 人工撤单；agent 账户 403 |

管理侧（`/admin` 权限）：

| 端点 | 说明 |
|---|---|
| `GET /admin/paper-trade/accounts` | 全平台账户（owner 用户名 + token 脱敏 + isAgent/enabled/lastSyncedAt/lastError） |
| `PUT /admin/paper-trade/accounts/{account_id}/agent` | `{isAgent}` 指定/取消；全局唯一 |
| `PUT /admin/paper-trade/accounts/{account_id}/enabled` | `{enabled}` 启停 |

### 6.5 前端

- **改名**：侧边栏菜单「模拟盘」→「模拟交易」（Sidebar、页面标题与文案、
  shared 注释、router 注释同步）。
- **账户选择器**（页头）：多账户下拉（agent 账户带「Agent」徽标）+「管理账户」入口
  （Modal/Drawer：列表 + 新建/编辑表单——name / token（密码框，编辑留空不改）/
  accountId；删除带二次确认与 409 提示）。
- **未配置引导**（`enabled:false`）：使用方法卡——掘金注册步骤
  （sim.myquant.cn 注册 → 个人中心取 token → 创建仿真账户取 account_id）+
  页内表单直达配置，配置成功即出数。
- **人工下单卡**：标的 / 方向 / 价格 / 数量 / 类型（限价/市价），确认后调
  `POST /paper-trade/orders`；未完结委托行加「撤单」按钮。agent 账户选中时
  下单卡禁用并提示「Agent 专属账户，人工下单已禁用」。
- **管理后台**：`/admin/paper-trade` 新页（路由 + Sidebar 管理组登记）——
  全平台账户表（owner / 名称 / counterAccountId / token 脱敏 / Agent 徽标 /
  启用态 / 最近同步 / 最近错误），行操作：指定/取消 Agent、启停。
- `shared/types/paperTrade.ts` 补账户 wire 类型；下单/撤单错误（403/409）用
  `message.error` 透出柜台或校验原文。

### 6.6 盘后同步多账户化

- `sync_daily` 外层循环所有 `is_enabled` 账户：单账户失败记录 `last_error` 并继续
  （错误隔离），其余账户正常落库；全局 `redis_lock` 不变。
- 账户级成功后回写 `last_synced_at` 并清 `last_error`；全部账户未配置时任务
  SKIPPED（原因写 message）。

**验收**：双用户各自配置账户互不可见（越权 404/403）；同一 counter account 二次
配置 409；人工对 agent 账户下单 403；指定第二个 agent 账户被唯一约束拦截；
下单→未完结委托可见→撤单→状态推进；token 全链路无明文（wire / 日志 / admin 列表）；
多账户同步单账户失败不阻塞其他账户；菜单与页面文案统一「模拟交易」。

## 7. 批次 4：人工交易体验优化（2026-09-24 需求扩展③，优先级前置）

优先级调整（D20）：先把人工模拟交易做到「好用」再开发 Agent 能力——对标同花顺
模拟交易的核心手动路径，把批次 3 交付的「能下单」升级为完整交易体验。全部作用于
用户自有非 agent 账户，不引入任何 agent 能力。

### 7.1 行情驱动的下单卡

- 行情条扩展：现价/涨跌幅之外补充 今开/最高/最低/昨收（既有 quote API 字段齐备），
  交易时段 30s 自动刷新（`useStockQuote` 既有行为）。
- **交易时段状态条**（`utils/beijing.ts` 判定）：交易中 / 午间休市 / 已收盘 / 未开盘。
  非交易时段限价单可挂（柜台接受、开盘撮合），页面明确提示「将开盘后撮合」；
  市价单非交易时段禁用并说明——根治「11:32 下单为何一直已报」类困惑。
- 涨跌停参考价：按昨收与板块规则计算（主板 ±10%、创业板/科创板 ±20%、ST ±5%
  按 quote 名称判定），下单卡展示上下限；越界价格前端即拦（柜台校验原文仍透传兜底）。
- **最大可买/可卖**：买入按 `floor(可用资金 / 现价 / 100) × 100` 一键填充
  （注明未含手续费）；卖出按持仓可用量（`availableVolume`，T+1）填充。
- **下单确认弹窗**：提交前复核 名称/方向/价格/数量/预估金额/可用资金，确认后才真实
  提交（对齐同花顺下单习惯）；下单卡常显可用资金。

### 7.2 持仓与下单联动

- 持仓表行内「买入/卖出」快捷按钮 → 回填下单卡（代码 / 方向 / 可卖量 / 现价代入），
  页内滚动聚焦下单卡。
- 卖出无持仓时前端即提示（柜台拒单原文仍透传兜底）。

### 7.3 委托状态自动推进

- 下单/撤单成功后**延迟补同步**（t+3s / t+15s 两次静默调 `POST /accounts/{id}/sync`）
  ——柜台撮合异步，状态推进无需手动刷新。
- 交易时段内委托 tab 30s 轮询本地表（`refetchInterval` + 交易时段判定）。
- 撤单按钮加 Popconfirm 防误触。

### 7.4 账户健康透明化

- 掘金 401（token 失效）定向提示：「token 已失效，请在账户配置中更新」，
  不再笼统报错；账户管理弹窗补 最近同步 / 最近错误 列（wire 已有
  `lastSyncedAt` / `lastError` 字段）。

**验收**：全流程走查——输码出行情条 → 现价代入 / 最大可买 → 确认弹窗 → 委托出现 →
Popconfirm 撤单 → 3s 内「已撤」推进；午间休市下单出现撮合提示；涨跌停越界被前端
拦截；token 失效提示明确；类型检查 / 单测绿。

**非目标**：五档盘口（平台行情源无买卖五档字段）；人工账户本地条件单/止盈止损监控单
（条件触发属 agent 计划执行域，列入 §13 扩展）；键盘快捷键下单。

## 8. 批次 5：交易 Agent 独立会话、专属工具与配置面（写路径）

交易 Agent 是系统级单例的独立 agent（D16-D18）：交易员人格、专属工具集、独立对话面，
与侧边栏助手不共享工具与对话；页面仅管理员可访问。

### 8.1 独立 Agent 运行时（复用线程基建）

- 复用现有助手线程 / runs / SSE / `ask_user` 基建，新增 **agent 类型**（`trading`）：
  线程与消息按类型隔离；后端会话端点按 admin 权限校验，前端路由走 `ProtectedAdmin`。
- 人格与规则：`app/prompts/agents/trading_agent.yaml`（应用基础设施 prompt 目录约定）——
  交易员定位（按计划交易、纪律优先、定期复盘总结）、操作边界（只操作 agent 专属账户、
  只读其他技能域数据）、拒单与风控转述规范。
- 对话写操作同样走 `ask_user` 问题卡确认（与侧边栏助手同底座，D5 ±3% 提示沿用）。

### 8.2 专属工具集（从侧边栏助手剥离）

- **剥离**：`build_assistant_tools()` 不再注册任何交易写工具；侧边栏助手继续负责
  复盘解读等既有技能，对话中涉及交易诉求时引导至交易 Agent 页。
- 交易 Agent 工具面**按批次渐进注册**（声明式注册表，每批次追加）：

| 批次 | 工具 | 性质 | 说明 |
|---|---|---|---|
| 5 | `get_paper_trade_account()` | 读 | 资金 + 持仓 + 未结委托（固定解析 agent 账户） |
| 5 | `place_paper_trade_order(symbol, side, volume, price, order_type)` | 写 | 校验 A 股 100 股整数倍；返回柜台委托对象（含 cl_ord_id）；拒单透传 `ord_rej_reason_detail`；`order_source='agent'` |
| 5 | `cancel_paper_trade_order(cl_ord_id)` | 写 | 撤单 |
| 5 | `get_stock_quote`（既有） | 读 | 下单前取现价（±3% 提示） |
| 7 | `make_trade_plan(...)` / `list_trade_plans()` / `cancel_trade_plan(id)` | 写/读 | 对话内制定 / 查询 / 取消当日计划（表为批次 7 数据底座） |
| 7 | `get_daily_review()` / `get_limit_up_attribution()` 等只读取数 | 读 | 复盘解读 / 涨停·异动归因产出（只读其他技能域，D16） |
| 9 | `recall_memories()` / `save_memory(...)` | 读/写 | 自有记忆检索与沉淀 |

- **工具保持薄，服务层承载逻辑**：工具层是「对话路径」与「批次 8 定时执行路径」
  共用的下单出口——风控硬校验（批次 8 定义）内聚在服务层下单函数，两条路径天然同规。
- 账户解析固定 `resolve_agent_account()`（批次 3）：工具不接收 accountId 参数；
  后台未指定 agent 账户时工具返回引导文案（请管理员在后台指定），不报 500。
- 下单 / 撤单成功后返回值携带
  `page_event("paper_trading.complete", action=..., cl_ord_id=..., symbol=...)`。

### 8.3 回写与订阅

- `pageEvents.ts` 登记表：`actionLabel: '查看交易 Agent'`，`path: '/trading-agent'`；
  `stores/assistant.ts` 的 `PageAssistantResult` 联合类型加分支。
- 交易 Agent 页 `usePageAssistantResult('paper_trading.complete')` 订阅 → 刷新执行动态
  + `message.success`。

### 8.4 `skills/paper-trading/SKILL.md`

frontmatter：`allowed-tools: get_paper_trade_account, place_paper_trade_order,
cancel_paper_trade_order, get_stock_quote, ask_user`（批次 7/9 工具就绪后追加）。

流程要点（写入 SKILL.md 规则节）：
1. 下单前必调 `get_stock_quote` 取现价；限价单价格偏离现价超过 ±3% 时在确认卡中
   显式提示（仅提示不阻断）。
2. **任何写操作前必须 `ask_user`**：问题卡列明 标的 / 方向 / 数量 / 价格 / 类型 /
   预估金额，默认选项为「确认下单」。
3. 拒单时向用户转述柜台原文（如涨跌停范围校验失败）。
4. 数量必须为 100 股整数倍；科创板 200 股起、以 1 股递增（工具层校验，Skill 转述）。
5. 交易对象固定为 agent 专属账户；不代用户操作其个人账户（引导其使用模拟交易页
   的人工下单入口）。
6. 交易员纪律：计划外的临时下单须在对话中说明理由（盘后复盘可追溯）；
   无计划交易日不主动开仓。

**验收**：管理员在交易 Agent 页对话「以现价买 100 股浦发银行」→ 弹确认卡 → 确认后
真实委托出现（`order_source='agent'`）→ 执行动态刷新；撤单同链路；侧边栏助手已无
交易工具；非 admin 访问 `/trading-agent` 被拒；未指定 agent 账户时工具给引导文案。

### 8.5 配置面（`trading_agent_config` 单例表）

迁移 `20260924b_trading_agent_config.sql`（幂等，同步 init-scripts，seed 默认行）：

```sql
CREATE TABLE IF NOT EXISTS trading_agent_config (
    id                     INTEGER      PRIMARY KEY,      -- 恒为 1 的单例行
    llm_config_id          BIGINT,                        -- 关联 llm_config；空 = 默认 chat 模型
    risk_max_position_pct  NUMERIC(5,2) NOT NULL DEFAULT 20,    -- 单票市值 ≤ 总资产 %
    risk_max_total_pct     NUMERIC(5,2) NOT NULL DEFAULT 80,    -- 总持仓 ≤ 总资产 %
    risk_max_daily_orders  INTEGER      NOT NULL DEFAULT 10,    -- 单日下单笔数上限
    auto_exec_enabled      BOOLEAN      NOT NULL DEFAULT TRUE,  -- 盘中自主执行总闸
    updated_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
```

- API：`GET/PUT /api/v1/admin/paper-trade/agent/config`（admin）。
- **模型选择**：对话 / 计划 / 复盘共用所选模型（`llm_config_id`，空 = 默认 chat）；
  服务层每次构建模型时读取，改选即时生效。
- **风控参数 DB 化**：批次 8 消费，env 覆盖退役（真相源唯一）。
- **自主执行总闸**：关闭时批次 8 轮询任务整体 SKIPPED（只保留对话手动交易路径）。
- 定时任务启停不进此配置——复用采集管理既有 `collector_task.enabled` 开关。
- 前端：交易 Agent 页「配置」区（模型下拉 + 风控数值输入 + 总闸 Switch）。
- 后端会话与工具构建读取本表决定交易 Agent 的模型；复盘任务（批次 6）同源。

## 9. 批次 6：模拟交易复盘（日/周/月，LLM，分层归因）

复盘对象固定为 **agent 专属账户**（本地三表按 `resolve_agent_account()` 过滤）；
人工账户不做 LLM 复盘（非目标），仅页面数据展示。

- 复盘周期 `period: day | week | month`（日度为主，周/月汇总）：
  - 输入窗口按周期取本地表区间（day = 当日；week = 本周一至今；month = 本月至今），
    资金曲线取 `paper_trade_cash_snapshot` 同区间，委托/成交按 `trade_date` 过滤
    （均限 agent 账户行）。
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
     experiences: [{title, body, mem_type}]}    # 批次 9 消费：经验提取（discipline|method|lesson）
    ```
    分层归因是批次 9 记忆沉淀精准反哺的前提（选股错→沉淀选股纪律；计划错→沉淀
    计划方法；执行错→沉淀执行纪律），一次 LLM 输出全部字段，不做二次调用。
- 定时：`paper_trade_review_1610`（heavy 队列，串行在 sync 之后；input_hash 缓存 +
  redis 并发锁，复用 review 服务层范式）。周/月不单独建 cron——同一任务内用
  `app.core.clock` 日历判定加发：周五盘后加发周度；月末最后一个交易日盘后加发月度
  （cron 表达不了"最后交易日"，任务内判定 + SKIP 复用既有机制）。
- 落库：复用 `ai_analysis_result`（`skill_id='paper-trade-review'`），不建新表；
  页面在交易 Agent 页内嵌「AI 复盘」卡片 + page_event。
- agent 账户当日无交易且无持仓时 SKIPPED（无复盘对象）。

**验收**：盘后自动生成复盘（分层 verdict 齐全）；同日重跑命中缓存；页面卡片展示；
周五/月末自动加发对应周期；人工账户数据不进入复盘输入。

## 10. 批次 7：Agent 选股与交易计划（闭环第一步）

### 10.1 数据底座

迁移 `20260924c_agent_trading_tables.sql`（幂等，同步 init-scripts）：

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

### 10.2 生成任务 `agent-daily-plan`（heavy 队列）

- seed：`('agent_daily_plan_1900', 'agent-daily-plan', 'internal', '0 19 * * 1-5', true)`
  ——北京 19:00（核心输入「当日复盘解读」18:35 才生成，早于该时点不存在），串行在
  16:00 sync / 16:10 复盘 / 16:30 涨停归因 / ≥17:45 异动之后；输入未就绪走
  `ReviewInputDataNotReadyError` 退避重试。
- spider：`backend/collector/spiders/agent_daily_plan.py`（internal，同先例）；TaskSpec
  追加进 `runtime/specs/trading.py`。
- 服务层 `app/services/trading/agent_plan_service.py`：
  1. **输入组装**：当日复盘解读全文（`ai_analysis_result`：market-daily-review）+
     涨停归因 groups/stock_codes + 异动归因 top-N + 当前模拟交易持仓
     （本地表，**agent 账户**行）+
     **人工移出历史**（`agent_stock_selection.removed_reason='manual'` 近期清单，
     prompt 显式声明避免重复选入）+ **方法论基座**（2026-09-26 方案 A 定版：
     温程《趋势理论》KB 直读双层注入——`point_type='discipline'` 全量条目 +
     发布目录树总纲 + 当日盘面文本按 method/theorem/concept/case 四类 RRF 检索，
     见 `agent_methodology`；`trading_agent_config.methodology_source_id` 指定
     知识源，空则降级无基座）+ Agent 经验记忆（`agent_memory` 中 `status='active'`
     条目，按新近度注入并做 token 上限截断；批次 9 之前该输入自然为空集，
     链路先行不阻塞）。
  2. **LLM 结构化输出**（`run_structured`，字段禁默认值）：
     `{selections: [{stock_code, reason, confidence}],
       plans: [{stock_code, plan_type, strategy, buy_zone_low/high, target_price,
                stop_loss, position_pct, basis}]}`——买卖点以当日收盘价为基准；
     每个持仓标的必须产出 sell 计划（含 stop_loss，执行纪律）。
  3. **落库与分组同步**：upsert `agent_stock_selection`（当日清单）+
     `agent_trade_plan`（全自主：生成即 `active` 生效）；agent 分组同步
     （选入加入 / 未续选且过期移出标 `removed`，人工移出不覆盖）。
  4. `redis_lock` + input_hash 缓存复用 review 范式；`paper_trade_url` 未配置或
     agent 账户未指定整体 SKIPPED。

### 10.3 前端（自选页内 Agent 分组）

- `Watchlist/index.tsx` 渲染 `owner_type='agent'` 分组：AI 徽标 + 选股依据
  （reason 摘要，展开看全文）+ 置信度；用户可移出（标 `removed_reason='manual'`），
  不可手动加入。此分组是交易 Agent 对非 admin 用户的唯一可见面（干预面，D17）。
- 交易 Agent 页加「今日交易计划」区块：计划列表（方向 / 买点区间 / 止盈 / 止损 /
  仓位 / 状态 / 依据），当日计划可人工 `cancelled`（干预手段之一）；
  对话路径的 `make_trade_plan` 等工具（§8.2 批次 7 行）同批注册。

**验收**：盘后 19:00 自动产出选股清单 + 计划；agent 分组与依据可见；人工移出后
次日不重复选入；重跑命中缓存；非交易日 SKIPPED。

## 11. 批次 8：盘中自主执行（闭环第二步）

### 11.1 执行任务 `agent-trade-exec`（batch 队列）

- seed：`('agent_trade_exec_5min', 'agent-trade-exec', 'internal', '*/5 9-14 * * 1-5',
  true)`——beat 每 5 分钟派发，**任务内判定交易时段**（9:30-11:30 / 13:00-15:00，
  `app.core.clock`，非时段 SKIPPED）；14:50 后进入「尾盘强检」模式（同一任务内分模式，
  避免双任务并发互斥）。`redis_lock` 防重入；非交易日 SKIPPED。
- 服务层 `app/services/trading/agent_exec_service.py`，单轮逻辑：
  1. 读当日 `active` 计划 → 逐计划 `get_stock_quote` 取现价；
  2. **条件判定**：buy 计划现价 ≤ `buy_zone_high` 触发买入（限价，价格 = 买点上限）；
     sell 计划现价 ≥ `target_price`（止盈）或 ≤ `stop_loss`（止损）触发卖出
     （限价，保护性偏离限幅）；
  3. **风控硬校验**（服务层内聚，与 LLM 无关，参数读 `trading_agent_config`，§8.5）：
     单票市值 ≤ 总资产上限%、总持仓 ≤ 总资产上限%、禁 ST/退市风险股、单日下单 ≤ 笔数上限、
     T+1（卖出标的必须是此前交易日买入——查本地 execution）、100 股整数倍、
     科创板 200 股起；任一不过则计划保持 active 并记录原因（不告警式失败）；
  4. **下单**（批次 5 服务层下单函数，`source='agent'`）→ 成功后推进计划
     `triggered` + 记 `triggered_cl_ord_id`，成交确认依赖 16:00 sync 回填；
  5. **尾盘强检**（14:50-15:00 窗口）：全部持仓对 `stop_loss` 强检一遍（含当日无
     sell 计划的持仓——按计划纪律兜底）；当日仍未触发计划标 `expired`。
- **总闸与参数**：任务入口先检 `trading_agent_config.auto_exec_enabled`（批次 5 建表，
  admin 可改，§8.5）——关闭整体 SKIPPED（只保留对话手动交易路径）；风控阈值读同表
  （seed 默认 20% / 80% / 10 笔），env 覆盖退役。

### 11.2 事后通知与可见性

- 不新建通知系统：执行动态集中在交易 Agent 页两处（admin 可见，D17）——
  1. 「今日交易计划」区块状态实时推进（triggered/executed）；
  2. 「Agent 执行动态」条（读 plan×order 关联：时间 / 标的 / 方向 /
     数量 / 价格 / 触发原因[止盈|止损|买点|尾盘强检]）。

### 11.3 盘中判定引入 Jev 的可行性调研（结论：暂缓，留缝）

调研结论（2026-09-24）：**核心触发判定维持确定性代码，本期不引入 Jev；在
`agent_exec_service` 预留可替换的条件判定缝，待其成熟与中文输入验证后再评估。**

- API 形态（官方）：`POST /v1/systemone`（Bearer），body `{state, model: "jev-latest",
  questions: {id: Question}}` → `{answers: {id: Answer}, usage}`。题型 `noul`（是非 →
  P(yes)）/ `choice`（单选）/ `score`（2-10 级有序打分），均带 confidence。
  ~250ms 延迟，$0.042/M input tokens（输出免费），单请求 64k token 预算（state+最长
  问句 ≤32k），1200 req/min——延迟与成本对 5 分钟轮询完全无压力。
- **根本不匹配**：批次 8 的条件判定是「现价 vs 阈值」数值比较，而 Jev 官方明确
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
  不动批次 8 其余部分。本批次不新增任何外部依赖。

**验收**：盘中模拟一个触达买点的标的 → 5 分钟内自主下单 → 计划状态推进 → 委托
落 `paper_trade_order`（agent 账户，`order_source='agent'`）→ 风控约束生效（构造超
仓位计划被拒）；尾盘强检与 expired 推进正确；非交易时段 SKIPPED。

## 12. 批次 9：经验沉淀闭环（复盘 → Agent 自有记忆 → 反哺）

记忆落 **Agent 自有记忆系统**（新表 `agent_memory`），不经 KB 知识库——记忆是
Agent 的私有资产，自动提取直接生效（无草稿/审核流转），人只做查看、停用与手动
补充三类干预。

> **2026-09-26 方案 A 定版——方法论与经验分层**：交易的方法论基座（温程
> 《趋势理论》整套体系）**不经 `agent_memory`，以 KB 为单一真相源直读注入**
> （纪律全量 + 目录树总纲 + 当日盘面 RRF 检索，`trading_agent_config.
> methodology_source_id` 绑定知识源，见 §10.2）；`agent_memory` 回归本职只装
> **迭代经验**（复盘沉淀 + 手动沉淀），经验可修正方法应用、不得违反纪律硬约束。
> 曾以 13 条蒸馏种子落 `agent_memory`（方案 C 试行），已由迁移
> `20260926f_agent_methodology_kb.sql` 下架。

### 12.1 数据底座

迁移 `20260926e_agent_memory.sql`（幂等，同步 init-scripts）：

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

### 12.2 自动提取（直接生效）

- 数据源：批次 6 复盘输出的 `experiences`（同一次 LLM 输出，无额外调用）。
- 复盘生成完成后直接写 `agent_memory`（`source='auto'`、`status='active'`）——
  分层归因决定 `mem_type`：选股错 → discipline（选股纪律）；计划错 → method
  （计划方法）；执行错 → discipline（执行纪律）；跨 trade 共性 → lesson。
- 幂等：按 `(source_result_id, title)` 去重，重跑不重复入库。

### 12.3 人工干预（查看 / 编辑 / 停用 / 手动沉淀）

- 交易 Agent 页「Agent 记忆」区块（admin-only，D17）：记忆列表（类型 / 标题 / 正文 /
  来源 / 状态），支持**编辑**（标题 / 正文 / 类型）与 `archived` 停用
  （不物理删除，保留归因链路）。
- 复盘卡片每条 trade verdict 与 overall 旁加「沉淀为记忆」按钮 →
  `POST /api/v1/admin/paper-trade/agent/memory`（admin 路径，服务层直写
  `agent_memory`，`source='manual'`、`status='active'`——管理员主动即生效）→
  `message.success`。前端对话框预填标题/正文（来自所选 verdict reason），可编辑后提交。
- 编辑与停用端点：`PUT /api/v1/admin/paper-trade/agent/memory/{id}`（编辑）、
  `PUT .../memory/{id}/status`（active/archived 切换）。

### 12.4 反哺闭合

- 批次 7 `agent-daily-plan` 的记忆检索输入（`status='active'`）在批次 9 供数后自然
  生效——**注入接线在批次 7 已完成，本批次只供数**。
- 闭环验证：复盘沉淀一条「追高风险」纪律记忆 → 次日选股/计划 prompt 引用该记忆
  （日志验证）；停用后次日不再引用。

**验收**：复盘后 experiences 自动进 `agent_memory` 且 active；停用一条记忆后次日
prompt 不再引用；手动沉淀一键 active（manual 标记）；重跑不重复入库。

## 13. 扩展（暂缓，不在本期）

- sidecar 增加 MCP streamable-http 端点，供外部 AI 客户端（如 Claude）直接交易。
- 出入金 API（`/v3/accounts/{id}/cash-inout`）与手续费设置对接。
- 实盘对接（复用风控纪律层 + 柜台适配器，另立方案）。
- 执行通知外扩（邮件 / webhook）；复杂策略引擎（网格 / 定投 / 再平衡）。
- 人工账户 LLM 复盘（当前复盘对象固定 agent 账户；需求出现时按账户维度扩展）。
- 人工账户本地条件单（止盈/止损价格监控触发下单），人工侧需求出现时另立方案评估。

## 14. 部署与验收纪律

- 迁移先于代码滚动（新表无热表 DDL 风险，仍按纪律先跑迁移再换镜像；批次 7 的
  `ALTER TABLE user_watchlist_group` 后重启 worker——asyncpg 语句缓存失效纪律）。
- 生产 `.env`：`PAPER_TRADE_URL` 保留；`GMTRADE_TOKEN` / `GMTRADE_ACCOUNT_ID`
  **退役不部署**（D12）；确认 `credential_encryption_key` 已设置（proxy 密码加密
  同源，token 解密依赖）。
- compose：paper-trade sidecar 服务移除凭证 env；web/worker/heavy 的
  `PAPER_TRADE_URL` 注入不变。
- 批次 5 迁移 seed `trading_agent_config` 默认行（风控 20% / 80% / 10 笔 + 总闸开）；
  风控参数真相源为 DB，不走 env。
- 每批次完成：`uv run mypy app/` + `uv run pytest -m unit` + `uv run ruff check .`；
  前端 `npm run build` + 类型检查。

## 15. 决策点记录（已全部拍板）

| # | 决策 | 结论 |
|---|---|---|
| D1 | 盘后同步时刻 | **16:00**（清算稳定 + 退避窗口足） |
| D2 | 模拟交易页入口形态 | **独立页 `/paper-trade`**，菜单名「模拟交易」 |
| D3 | 复盘产出粒度 | **日度为主 + 周度/月度汇总**——同一任务内 `app.core.clock` 日历判定加发，不单独建 cron |
| D4 | 复盘落库 | **复用 ai_analysis_result**（skill_id 区分） |
| D5 | 下单确认阈值 | **±3%，仅提示不阻断** |
| D6 | 定时执行确认模式 | **全自主 + 事后通知**——计划生成即生效，不设人工审批；执行动态经页面可见（§11.2），人工干预手段 = 移出自选 / 取消计划 |
| D7 | agent 分组形态 | **现有自选页内 Agent 分组**（`owner_type='agent'`），AI 徽标 + 依据可见，可移出不可加入 |
| D8 | 记忆沉淀语义 | **落 Agent 自有记忆（`agent_memory`），不经 KB 审核流**：自动提取直接 active + 手动沉淀 active（source 标记区分）；人工干预 = 查看 / 停用 |
| D9 | 盘中触发方式 | **5 分钟条件轮询 + 14:50 尾盘强检**（单任务内分模式） |
| D10 | 执行自主度风控 | 服务层硬校验参数化：单票 ≤20% / 总仓 ≤80% / 单日 ≤10 笔 / 禁 ST / T+1（默认值可在实施时调整） |
| D11 | 盘中判定引入 Jev | **暂缓，留缝**——数值比较超出 Jev 能力边界，核心判定维持确定性代码；`agent_exec_service` 条件判定预留纯函数缝，待中文输入验证与产品成熟后再评估（§11.3） |
| D12 | 柜台凭证配置 | **入库配置，env 退役**——`paper_trade_account` 表（token Fernet 加密，复用 utils/crypto 与 proxy 先例）；sidecar 无状态化，凭证每请求头传递；`GMTRADE_TOKEN`/`GMTRADE_ACCOUNT_ID` 不再部署，`PAPER_TRADE_URL`（部署拓扑）保留 env |
| D13 | 多租户账户 | **每用户自有账户自配**（页内配置入口，未配置展示使用方法引导）；页面按账户展示（多账户选择器）；counter account 全局唯一防共享；每用户上限 10 个；有本地数据的账户只可停用不可删 |
| D14 | 人机账户关系 | **人机分账户**——agent 账户后台指定且全局唯一（部分唯一索引兜底），人工下单/撤单对其禁用（403）；人用自有其他账户手动交易，双净值曲线可对比；委托表 `order_source`（manual/agent）留归因过滤基础 |
| D15 | 人工交易入口 | **模拟交易页下单卡 + 未完结委托撤单**（限价/市价 × 买/卖），仅限自有非 agent 账户；不做改单（撤单重下替代）；用于验证模拟交易链路可用性 |
| D16 | 交易 Agent 定位 | **系统级单例独立 agent（不多租户）**——模拟一名交易员；与侧边栏助手及每日复盘/个股复盘/涨停归因等技能域解耦：只读其产出数据、不回写，产物一律落自有域（计划/选股/复盘/记忆）；主能力 = 按计划交易 + 定期复盘总结 |
| D17 | 前端承载与权限 | **独立页「交易 Agent」（`/trading-agent`，admin-only）**：对话 + 今日计划 + 执行动态 + 复盘 + 记忆（可见可编辑可停用）+ 配置；模拟交易页保持纯账户数据；工作台卡片取消；对非 admin 的唯一可见面 = 自选页 agent 分组（干预面） |
| D18 | 工具归属 | **交易写工具从侧边栏助手剥离，交易 Agent 专属**（工具面按批次渐进注册）；对话路径（ask_user 确认）与定时路径（全自主）共用服务层下单出口；复用现有线程/runs/SSE/ask_user 基建，新增 agent 类型隔离 |
| D19 | 配置面 | `trading_agent_config` 单例表（admin 可改）：**模型选择**（关联 llm_config，对话/计划/复盘共用）+ **风控参数**（单票/总仓/单日笔数，DB 真相源）+ **自主执行总闸**（关闭则批次 8 轮询 SKIPPED）；定时任务启停复用采集管理既有开关，不重复建设 |
| D20 | 批次优先级 | **人工交易体验先行**（2026-09-24）——新增批次 4「人工交易体验优化」（§7），Agent 闭环（会话/复盘/选股计划/执行/记忆）整体顺延为批次 5-9；人工体验对标同花顺核心路径（行情驱动下单 / 确认弹窗 / 状态自动推进 / 账户健康透明），不做五档盘口与人工条件单 |
