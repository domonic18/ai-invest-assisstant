# 异动分析架构设计（板块 / 个股）

> 闭环：盘后规则算子检测异动（What）→ top-N LLM 归因（Why）→ `/anomaly` 单页双 Tab 展示 → 侧边栏手动重分析。
> 方法论参照温程《股市趋势交易大师》趋势交易体系：M60 生命线为趋势分界、有效突破为启动确认、量为价先（2026-09-22 起融入检测与归因，见 §2）。

## 1. 设计原则

1. **检测与归因严格分层**：规则算子回答 What（确定性、可单测、零 token）；LLM 只回答 Why，不参与异动判定（仅可校正规则给出的分类）。
2. **检测数据源自包含**：趋势事实（日 K / 周 K 派生）+ 量价（全市场快照、板块收盘快照、新浪日 K）。资金流、涨停池、龙虎榜、公告、新闻**一律不进入检测链路**——异动判定不受外部事实源可得性影响，规则可离线单测。
3. **归因证据自由**：归因 LLM 经工具引用新闻 / 公告 / 龙虎榜 / 资金流 / 技术面 / 知识库作为证据，但证据只出现在归因文本中，不落检测表、不影响强度分。
4. **趋势上下文一票否决方向感**：同样的量价命中，多头趋势中是「启动 / 加速」，空头趋势中是「反抽 / 破位」，按分类降权而非等同呈现。

## 2. 趋势事实层（2026-09-22 引入）

`services/market/trend_facts.py` 纯函数 `compute_trend_facts(bars)` 从日 K 序列派生 `TrendFacts`，是复盘文本、异动检测、AI 归因三方共用的趋势口径（自 `index_technical_service` 提取为独立模块，提取前后输出逐字节一致）：

- **通道归属**（四态）：上升 / 下降 / 阻尼 / 交错；配合 MA10 / MA30 / MA60 位置
- **量能状态**：量比（当日量 / 5 日均量）、20 日地量标记
- **关键价位**：20 日新高 / 新低、60 日前低支撑及 1.5% 临近判定
- **周线位置**：周线 MA60 与 `above_weekly_ma60` 三态（True / False / None——不足 60 周的次新股为 None，不参与门控）
- **拐点列表** `turning_points`（三类，均要求量能确认）：

| 拐点 | 定义 | 量能确认 |
|------|------|----------|
| `support_test` 支撑试探 | 下降 / 阻尼通道回踩 60 日支撑带（含 1.5% 临近） | 缩量（≤ 0.7 × 5 日均量，或 20 日地量） |
| `breakout` 有效突破 | 带量收复 MA30，或带量创 20 日新高 | ≥ 1.3 × 5 日均量；**且收盘在周线 MA60 之上才成立**（周线下方的假突破被剔除） |
| `risk_break` 风险破位 | 上升通道中放量跌破 MA30 | 放量 |

> 周线 M60 门控语义：`above_weekly_ma60 = False` 时 `breakout` 拐点不成立（从 `turning_points` 剔除）；`None`（次新股）与 `True` 不门控。风险 / 支撑拐点不受周线门控。

## 3. 板块异动检测

数据源为 `quote_sector_daily`（行业 + 概念收盘快照），检测池收敛到**同花顺指数同名覆盖的板块**（一级行业 + 概念，宇宙取自 `quote_kline_sector_daily`，保证榜单板块的详情页均有真实指数 K 线），盘后对该池跑**四维判定**：

| 维度 | 规则 | 赋分 | 说明 |
|------|------|------|------|
| 齐动性 | `up_count / (up_count + down_count) ≥ 80%` | 35 | 板块内部同向度，来自快照涨跌家数 |
| 涨跌幅偏离 | `abs(change_pct) ≥ 2%` | 25 | 价格触发维度 |
| 趋势拐点 | 板块指数日 K 经 `compute_trend_facts` 算出 `turning_points` 非空 | 25 | THS 板块日 K（17:30 就绪）计入当日 bar；缺 K 线时该维跳过不抛错 |
| 量能异常 | `amount ≥ 5 日均额 × 2` | 15 | 基线取 `quote_kline_sector_daily` 近 5 个交易日均额；基线缺失或有效天数 < 5 时该维跳过 |

命中的维度列表写入 `anomaly_types`（多维齐中额外 +10）；赋分加权为 `strength`（0-100）。检测结果连同板块趋势事实落 `trend_facts` JSONB。

## 4. 个股异动检测

全市场日 K 不在库（`kline` 任务默认只采自选股），采用**两段式管线**：

```
全市场快照初筛                      候选精算
 ak.stock_zh_a_spot  ──阈值预筛──▶  候选集（强度预分排序，cap 250）
 涨幅/换手/量一次拉取                逐股拉新浪日 K（60+ 根，接口自带完整历史）
                                    ↓
                                    compute_trend_facts（通道 / 拐点 / 量能 / 周线门控）
                                    ↓
                                    规则判定 → 落库 market_anomaly_stock
```

| 维度 | 规则 | 分值 | 说明 |
|------|------|------|------|
| 有效突破拐点 | `breakout`（§2 定义） | 40 | 触发维度之首 |
| 风险破位拐点 | `risk_break`（§2 定义） | 30 | |
| 支撑试探拐点 | `support_test`（§2 定义） | 25 | |
| 量比异常 | 当日量 ≥ 5 日均量 × 2.5 | 25 | |
| 换手异常 | `turnover_rate ≥ 8%` | 20 | |
| 涨幅触发 | `abs(change_pct) ≥ 6%` | 15 | |

- **趋势上下文修正**：上升通道 +5；下跌趋势中命中的量价维度按反抽逻辑 ×0.7 降权。
- **周线门控**：`above_weekly_ma60 = False` 时 `breakout` 不触发（不足 60 周次新股不门控）；风险 / 支撑拐点不受限。
- **降级兼容**：`ma60` / `is_above_ma60` / `ma60_breakout` 保留为存量 wire 字段，前端展示用，**不再参与计分**。
- K 线不足 61 根时趋势维不可判定，量价维照常判定。
- 候选 K 线走新浪接口实时拉取，不受库内 K 线覆盖（自选股范围）限制；每日 API 量 = 1 次全市场快照 + 候选数次日 K，量级可控。

## 5. 异动分类

分类由**检测器规则即时写入** `attribution_category`，AI 归因仅可校正（校正结果覆盖回写），不负责首次分类：

- **板块二分**：`resonance` 趋势共振（多维度齐中）/ `rotation` 轮动补涨（单一维度、涨幅边际命中）。
- **个股四分**：`breakout` 趋势突破启动（有效突破拐点）/ `acceleration` 趋势内加速（多头趋势 + 量价命中）/ `pullback` 下跌反抽（空头背景，弱信号降权）/ `breakdown` 破位下行（风险拐点为独立强信号，**不按反抽打折**）。

## 6. 定时任务与调度

| 任务 | 渠道 | 队列 | 节奏 |
|------|------|------|------|
| `sector-anomaly`（板块异动检测） | internal | heavy | 交易日 **17:45**（依赖 17:30 THS 板块日 K 就绪，供趋势拐点维） |
| `stock-anomaly`（个股异动检测） | internal | heavy | 交易日 17:00（收盘日 K 就绪） |

- 两个任务均为「规则检测 + top-N 归因」串行：规则算子产出全量异动清单后，对 `strength` 排序 top-N（板块 10 / 个股 20）批量归因，单次 LLM 调用。
- 上游未就绪（全市场快照 / 板块快照缺失）抛 `NotReady` 异常 → Celery 600s × 3 退避重试（同涨停归因任务惯例）。
- 检测幂等：按 `(trade_date, 代码)` upsert，重跑覆盖；归因底稿写 `ai_analysis_result`（`input_hash = sha256(skill + domain + code + 日期 + :v3: 提示词版本盐)`），已生成直接复用；prompt 版本升级（如 2.1.0 引入周线语境）换盐整体失效旧缓存。
- 检测阈值（涨跌幅 / 量比 / 换手 / 齐动性、候选 cap、top-N）声明为任务 `config_params` 默认值，调参不改代码。

## 7. AI 归因

`anomaly-attribution` skill（scenario=market），两条路径共用同一 SKILL.md 与服务层（见 [CLAUDE.md](../../CLAUDE.md) AI 交互范式）：

- **自动路径**：检测任务尾部对 top-N 批量归因，LLM 结构化输出 `category + summary`，summary 回写检测行归因字段；清单中携带检测器规则分类（`rule_category`）供 LLM 校正。
- **手动路径**：页面「AI 归因」按钮 → `useAssistantStore.sendQuestion()` → 助手 agent 按 SKILL.md 取证分析 → persist 工具（`persist_sector_anomaly_attribution` / `persist_stock_anomaly_attribution`）写库并返回 `__event__`（`page_event("sector_anomaly.complete" / "stock_anomaly.complete")`）→ SSE 回写前端刷新。
- **证据工具**：资讯查询（电报 / 新闻文档）、公告、龙虎榜、资金流（个股 / 板块主力净流入）只读查询，另有 `get_stock_technical`（趋势位置，与检测 `trend_facts` 同口径交叉核实）与 `search_knowledge_base`——证据仅用于归因文本引用。
- **方法论注入**：`skills/anomaly-attribution/methodology.md`（趋势理论 L0 蒸馏手册）随提示注入，要求先把异动放回趋势位置（通道 / 拐点 / 量能）再取证。复盘类技能（market-daily-review / stock-daily-analysis）共用同一手册与引用契约。
- **知识库引用契约**：summary 涉及趋势 / 拐点判断时须内嵌 `《趋势理论》第N集 MM:SS（章节）` 引用（集数 / 时间码只能来自 methodology.md 尾注或知识库检索结果）；无适用方法论时输出 `> 知识库佐证：无适用方法论`。服务端 `_enforce_kb_citation` fail-soft 校验（缺失补 sentinel、只告警不失败）。
- SKILL.md 的 allowed-tools 列两条路径工具并集（含 persist 工具与证据查询工具）；结构化输出 schema 字段不带默认值。

## 8. 数据模型

### 8.1 market_anomaly_sector（板块异动日表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL pk | |
| trade_date | DATE NOT NULL | 交易日 |
| sector_type | VARCHAR(10) NOT NULL | industry / concept（对齐 `quote_sector_daily`） |
| sector_code / sector_name | VARCHAR | 板块标识与名称 |
| change_pct | NUMERIC(8,4) | 当日涨跌幅 % |
| amount | NUMERIC(20,2) | 当日成交额 |
| amount_ratio | NUMERIC(8,2) | 当日额 / 5 日均额 |
| up_count / down_count | INT | 板块内上涨 / 下跌家数 |
| anomaly_types | JSONB `'[]'` | 命中维度列表 |
| trend_facts | JSONB | 板块指数趋势事实（通道 / 拐点 / 量能摘要） |
| strength | INT NOT NULL | 强度 0-100 |
| attribution_category | VARCHAR(20) | resonance / rotation（检测时写规则分类，归因可覆盖） |
| attribution_summary | TEXT | 归因摘要（可空） |

约束：`uq_market_anomaly_sector(trade_date, sector_type, sector_code)`；审计字段 `created_at / updated_at`。

### 8.2 market_anomaly_stock（个股异动日表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL pk | |
| trade_date | DATE NOT NULL | 交易日 |
| stock_code / stock_name | VARCHAR | 标的标识与名称 |
| close | NUMERIC(12,4) | 收盘价 |
| change_pct | NUMERIC(8,4) | 当日涨跌幅 % |
| turnover_rate | NUMERIC(8,4) | 换手率 % |
| volume_ratio | NUMERIC(8,2) | 量比（当日量 / 5 日均量） |
| ma60 | NUMERIC(12,4) | 当日 MA60 值（兼容保留，不计分） |
| is_above_ma60 | BOOLEAN DEFAULT FALSE | 兼容保留，不计分 |
| ma60_breakout | BOOLEAN DEFAULT FALSE | 兼容保留，不计分 |
| anomaly_types | JSONB `'[]'` | 命中维度列表 |
| trend_facts | JSONB | 个股趋势事实（通道 / 拐点 / 周线门控结果） |
| strength | INT NOT NULL | 强度 0-100 |
| attribution_category | VARCHAR(20) | breakout / acceleration / pullback / breakdown（检测时写规则分类，归因可覆盖） |
| attribution_summary | TEXT | 归因摘要（可空） |

约束：`uq_market_anomaly_stock(trade_date, stock_code)`；审计字段同上。

## 9. 前端页面

- `/anomaly` **单页双 Tab**（板块 / 个股），Tab 切换走路由（`/anomaly/sector` | `/anomaly/stock`，URL 可直达）；侧边栏「检测」分组单入口。
- 页面结构：交易日切换 + 异动榜表格（`strength` 排序、`anomaly_types` 筛选、分类徽标、趋势事实摘要）+ 归因摘要列 + 行内「AI 归因」按钮（侧边栏手动重分析）；命中自选股的标的做关联标注。
- 衔接跳转：个股异动行点击直达个股详情；板块命中已建产业链图谱的行业时提供产业链全景直达链接（衔接 F-AI-01）。
- wire 走 camelCase（`CamelModel` + `shared/types` 单一真相源）；事件订阅走 `pageEvents.ts` 注册表 + `usePageAssistantResult`。

## 10. 后续文档索引

- [01-data-source.md](./01-data-source.md) — 数据源（全市场快照 / 新浪日 K / 板块快照 / THS 板块日 K）
- [02-data-collection.md](./02-data-collection.md) — 采集引擎与定时任务范式
- [03-data-storage.md](./03-data-storage.md) — 命名约定与 `ai_analysis_result` 缓存
- [04-ai-agent.md](./04-ai-agent.md) — Skill 体系与侧边栏 Agent
- [05-web-frontend.md](./05-web-frontend.md) — 前端架构与页面范式
- [12-knowledge-base.md](./12-knowledge-base.md) — 知识库（归因引用契约的检索底座）
