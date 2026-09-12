# AI 选股（问财筛选）方案

> 状态：方案定稿，待实施（2026-09-11）
> 定位：agent 即席选股能力 + 前端临时结果表 + 勾选入自选分组；结果为临时性内容，**零落库**

## 1. 背景与调研结论

问财 SkillHub 技能（`hithink-zhishu-query`）背后的核心是 NL2Data 网关：

- 端点：`POST https://openapi.iwencai.com/v1/query2data`
- 认证：`Authorization: Bearer <IWENCAI_API_KEY>` + 7 个 `X-Claw-*` 头（Skill-Id 固定 `hithink-zhishu-query`、64 字符 Trace-Id `secrets.token_hex(32)`、Call-Type `normal`/`retry`）
- 请求体（全 string）：`{query, page, limit, is_cache: "1", expand_index: "true"}`
- 响应：`datas[]`（中文列名行）、`code_count`（命中总数，分页用）、`chunks_info`（问句解析子句及各条件中间命中数，调试利器）
- 空结果协议：改写放宽问句重试 ≤2 次（Call-Type=retry）；引用数据须标注"来源于同花顺问财"

**实测（2026-09-11，三类惯用选股方法全部通过，延迟 0.9~2.3s）**：

| 方法 | 问句要点 | 命中 | 返回字段 |
|------|----------|------|----------|
| 技术复合 | 周线M60之上 + 上市>2年 + 非ST/北交所/次新 + 指定日/区间涨幅 + 近月有涨停 | 11 | 周线MA60值、区间涨跌幅、上市日期 |
| 涨停日 | 指定日涨停 + 排除项 | 48 | 封成比、几天几板、开板次数、最终封板时间 |
| 财务质量 | 2024年扣非/净利≥0.7 + 经营现金流/扣非≥0.7 + 收现/营收≥0.7 + 负债率<60% | 2117 | 跨表比率原值 + 分子分母 |

关键事实：

- 网关不按技能名限域，指数技能 id 照跑全市场个股筛选
- 跨字段派生比率引擎原生计算（本地需三表 join）
- 股票代码带 `.SH/.SZ` 后缀，交易所/ST/次新为结构化布尔字段
- 问句措辞敏感（"申万一级行业指数" 0 结果，改写后命中），日期须显式年份
- SSE 透传已验证：`runs.py` 补发 custom 事件走 `wire.jsonable()` 递归序列化，dict/list 原样通过 → **事件载荷可直接携带全量行数据**

## 2. 方案原则

1. **结果零落库**：筛选是即席动作，结果"存储介质"= SSE 事件流 + 前端 SPA 会话内存，用完即弃
2. **零新范式**：完全复用「侧边栏 Agent 触发 + page_event 回写」与自选分组既有链路
3. **不做 schema 归一**：中文列名原样透传（服务端不结构化消费问财数据），表格列由元数据驱动动态渲染
4. **只封装一个通用工具**：问财本质是任意条件组合，三类方法只是惯用 pattern，不按方法硬编码

## 3. 总体链路

```
用户（/screening 页按钮 或 侧边栏任意页对话）
  → sendQuestion("帮我筛选…")
  → assistant 调 screen_stocks(query, limit)          ← 问财网关（重试协议在服务层）
  → 工具返回值 = agent 叙述用文本 + __event__（携带全量结构化数据搭车）
  → SSE custom 事件 {query, total, truncated, columns[], stocks[]}
  → pageEvents 注册表解析 → 对话内「查看筛选结果」按钮
  → /screening 页挂载 → usePageAssistantResult 消费 → screening 临时 store
  → AntD 动态列表格 → rowSelection 勾选
  → 「加入自选分组」弹层（可输新组名）→ batchAddWatchlist（既有 API）
```

## 4. 后端设计（2 个新件）

### 4.1 问财客户端 `backend/app/services/market/iwencai_service.py`

- `query2data(query, limit, page=1) -> {datas, code_count, chunks_info}`：httpx POST，30s 超时
- 重试协议在服务层：`datas` 为空 → 放宽改写重试 ≤2 次（Call-Type=retry）；改写由调用方（工具层）传入候选问句
- Redis 缓存：按 query 哈希为键，盘中 TTL ~5min、盘后更长（防配额消耗，非持久化）
- 配置：`IWENCAI_API_KEY` 进 settings（env 注入，遵循 env 分层约定）；base URL 常量入 constants
- 服务层保持纯净：不导入 `app.agent.*`

### 4.2 筛选工具 `backend/app/agent/tools/screening_tools.py`

`screen_stocks(query: str, limit: int = 30) -> dict`，注册进 `build_assistant_tools()`：

1. 调 `iwencai_service`（缓存优先）
2. 代码归一：`000523.SZ → 000523`（与自选表 6 位格式对齐，归一在此单点完成）
3. 行键派生 `columns` 元数据：按行内首次出现顺序，排除 股票代码/股票简称 两个固定列
4. 行数上限 **50**：超出截断并置 `truncated=true`；返回给 agent 的文本包含"命中 total 只，已返回前 50，建议收敛条件"提示
5. 返回值：`{文本摘要, __event__: page_event("stock_screening.complete", query=…, total=…, truncated=…, columns=[…], stocks=[{stock_code, stock_name, **原始字段}])}`

工具 docstring 固化问句规则（agent 组织 query 时遵守）：

- 日期必须显式年份（"8月19日" → "2026年8月19日"）
- 主动补充排除项确认（非ST / 非北交所 / 非次新）
- 财务比率类筛选提醒负值陷阱（净利润为负时"扣非/净利≥0.7"双负得正，应加"净利润大于0"）
- 命中数 >limit 时引导用户收敛条件或提高 limit（上限 50）
- 答复中标注数据来源于同花顺问财

**不新建**：迁移 / ORM / persist 工具 / 查询路由 / shared API 类型。

## 5. 前端设计（4 个新件）

### 5.1 事件注册

- `web/src/components/assistant/pageEvents.ts`：新增 `stock_screening.complete` 定义——parse 直透 `{query, total, truncated, columns, stocks}`；actionLabel「查看筛选结果」；path `/screening`
- `web/src/stores/assistant.ts`：`PageAssistantResult` 联合类型加对应分支

### 5.2 临时结果 store `web/src/stores/screening.ts`（新建）

- 仅存最近一次筛选结果（SPA 会话级，关标签页即清）
- 独立 slice 的原因：`usePageAssistantResult` 消费即清空 assistant store，页面需要接住数据

### 5.3 筛选结果页 `web/src/pages/Screening/`

- 空态 + 「AI 选股」按钮（`useAssistantStore.getState().sendQuestion(...)` 范式，见 `LimitUpSection.tsx`）
- `usePageAssistantResult('stock_screening.complete', cb)`：cb 内写入 screening store + `message.success` + return true；面板关闭时经 panelOpen effect 复位"生成中"状态
- AntD Table + 动态列（由 `columns` 元数据生成）：
  - 固定列：股票代码、股票简称（置首）
  - 已知中文列映射表（本页 `columns.tsx` 收敛）：最新价（2dp）、涨跌幅（百分比 + 走 formatters 的 scheme-aware 红涨绿跌，`useColorScheme()` 订阅）、封成比/几天几板等按需补充
  - 未知列纯文本兜底（问句变了表格不崩）
- rowSelection（先例 `Watchlist/ScreenshotImportModal.tsx` 的 `selectedCodes: Set<string>`）
- 工具栏「加入自选分组」：分组选择弹层（支持输入新组名，`batchAddWatchlist({items, groupId?, newGroupName?})` 已支持）→ 按 created/duplicated 计数提示；自选页数据由既有 invalidate 链路刷新
- `truncated=true` 时表格顶部 Alert：命中 total 只，仅展示前 50，建议收敛条件

### 5.4 路由与导航

- `/screening` 路由注册 + 侧边栏菜单项

## 6. 时序细节（沿用既有机制）

- 事件到达时用户在别处：结果滞留 assistant store，对话内按钮点击 → 导航 `/screening` → 页面挂载时 `usePageAssistantResult` 才消费（pending 等待机制现成）
- 用户就在 /screening 触发：挂载中的订阅立即消费，表格就地刷新
- 会话重放不重发事件（custom 事件仅流式运行时补发），符合临时语义；对话中 agent 的文字分析随 checkpointer 持久，可回看

## 7. 边界与取舍

- **F5 后结果不可恢复、无历史回看**：本方案立意即临时性，非缺陷；升级路径 = iwencai_service 加 Redis TTL（如 2h）+ `GET /screening/last` 端点，工具与服务层零改动
- 事件载荷 ~15KB（50 行）量级，SSE 无压力
- 配额风险：Redis query 缓存兜底；工具层 30s 超时；不设并发放大（单用户会话内串行）
- 数据可信：结果仅作 agent 即席证据与人工参考，不进检测/复盘等结构化管线（与异动检测方法论"自包含"口径无冲突）

## 8. 实施顺序与验收

顺序：后端 service + 工具 → 前端事件注册 → 筛选页 → 联调。

验收基线：`uv run mypy app/`、`uv run pytest -m unit`、`uv run ruff check .`；`npm run typecheck / lint / test / build`；三类惯用方法实测出表、勾选入自选、重复加入提示 duplicated、刷新后空态引导正常。

工作量：后端约 0.5 天，前端约 0.5 天。

## 9. 后续扩展（触发条件再立项）

| 项 | 触发条件 |
|----|----------|
| 结果暂存（Redis TTL + last 端点） | 刷新不丢成为真实诉求 |
| 定时自动筛选（如技术复合法每日收盘自动跑） | 需要每日候选清单；接线 = TASK_SPECS internal spec + seed cron + registry 登记 executable skill + persist 落库（届时才需要表） |
| 常用筛选条件模板（保存问句） | 模板即一段 prompt 文本，可先落在前端 localStorage 验证价值 |
