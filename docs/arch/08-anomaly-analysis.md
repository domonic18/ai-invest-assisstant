# 异动分析架构设计（板块 / 个股）

> 闭环：盘后规则算子检测异动（What）→ top-N LLM 归因（Why）→ `/anomaly` 双页展示 → 侧边栏手动重分析。
> 方法论参照温程《股市趋势交易大师》趋势交易体系：M60 生命线为趋势分界、有效突破为启动确认、量为价先。

## 1. 设计原则

1. **检测与归因严格分层**：规则算子回答 What（确定性、可单测、零 token）；LLM 只回答 Why，不参与异动判定。
2. **检测数据源自包含**：仅趋势（MA60）+ 量价（新浪日 K、全市场快照、板块收盘快照）。资金流、涨停池、龙虎榜、公告、新闻**一律不进入检测链路**——异动判定不受外部事实源可得性影响，规则可离线单测。
3. **归因证据自由**：归因 LLM 经工具引用新闻 / 公告 / 龙虎榜 / 资金流作为证据，但证据只出现在归因文本中，不落检测表、不影响强度分。
4. **趋势上下文一票否决方向感**：同样的量价命中，多头趋势中是「启动 / 加速」，空头趋势中是「反抽」，按分类降权而非等同呈现。

## 2. 板块异动检测

数据源为 `quote_sector_daily`（行业 + 概念收盘快照），检测池收敛到**同花顺指数同名覆盖的板块**（一级行业 + 概念，宇宙取自 `quote_kline_sector_daily`，保证榜单板块的详情页均有真实指数 K 线），盘后对该池跑三维判定：

| 维度 | 规则 | 说明 |
|------|------|------|
| 涨跌幅偏离 | `abs(change_pct) ≥ 2%` | 价格触发主维度 |
| 量能异常 | `amount ≥ 5 日均额 × 2` | 基线取 `quote_kline_sector_daily`（THS 板块日 K，约一年历史）同板块近 5 个交易日均额；快照表无历史积累不构成冷启动障碍。基线缺失或有效天数 < 5 时该维度跳过，其余维度正常判定 |
| 齐动性 | `up_count / (up_count + down_count) ≥ 80%` | 板块内部同向度，来自快照涨跌家数 |

命中的维度列表写入 `anomaly_types`；各维度命中赋分加权为 `strength`（0-100，齐动性权重最高，涨跌幅次之）。

## 3. 个股异动检测

全市场日 K 不在库（`kline` 任务默认只采自选股），采用**两段式管线**：

```
全市场快照初筛                      候选精算
 ak.stock_zh_a_spot  ──阈值预筛──▶  候选集（强度预分排序，cap 250）
 涨幅/换手/量一次拉取                逐股拉新浪日 K（60+ 根，接口自带完整历史）
                                    ↓
                                    MA60 趋势状态 / 有效突破 / 量比 / 换手精算
                                    ↓
                                    规则判定 → 落库 market_anomaly_stock
```

| 维度 | 规则 | 类型 |
|------|------|------|
| 有效突破 M60 | 当日收盘**首次**站上 MA60 且量比 ≥ 2 | 触发（`ma60_breakout`） |
| 量比异常 | 当日量 ≥ 5 日均量 × 2.5 | 触发 |
| 换手异常 | `turnover_rate ≥ 8%` | 触发 |
| 涨幅触发 | `abs(change_pct) ≥ 6%` | 触发 |
| 趋势状态 | `close` vs MA60 → 多头 / 空头背景 | 上下文（不单独触发，决定分类与加权方向） |
| 趋势过滤 | 空头背景下命中量价维度 → 归类「下跌反抽」并降权 | 上下文 |

候选 K 线走新浪接口实时拉取，不受库内 K 线覆盖（自选股范围）限制；每日 API 量 = 1 次全市场快照 + 候选数次日 K，量级可控。

## 4. 异动分类

- **板块二分**：`resonance` 趋势共振（涨跌幅 + 量能 + 齐动多维度齐中）/ `rotation` 轮动补涨（单一维度、涨幅边际命中）。
- **个股三分**：`breakout` 趋势突破启动（有效突破 M60）/ `acceleration` 趋势内加速（多头趋势 + 量价命中）/ `pullback` 下跌反抽（空头背景，弱信号标注）。

## 5. 定时任务与调度

| 任务 | 渠道 | 队列 | 节奏 |
|------|------|------|------|
| `sector-anomaly-detect`（板块异动检测） | internal | heavy | 交易日 16:45（板块收盘快照落库后） |
| `stock-anomaly-detect`（个股异动检测） | internal | heavy | 交易日 17:00（收盘日 K 就绪） |

- 两个任务均为「规则检测 + top-N 归因」串行：规则算子产出全量异动清单后，对 `strength` 排序 top-N（板块 10 / 个股 20）批量归因，单次 LLM 调用。
- 上游未就绪（全市场快照 / 板块快照缺失）抛 `NotReady` 异常 → Celery 600s × 3 退避重试（同涨停归因任务惯例）。
- 检测幂等：按 `(trade_date, 代码)` upsert，重跑覆盖；归因底稿写 `ai_analysis_result`（`input_hash = sha256(skill + domain + code + 日期)`），已生成直接复用。
- 检测阈值（涨跌幅 / 量比 / 换手 / 齐动性、候选 cap、top-N）声明为任务 `config_params` 默认值，调参不改代码。

## 6. AI 归因

`anomaly-attribution` skill（scenario=market），两条路径共用同一 SKILL.md 与服务层（见 [CLAUDE.md](../../CLAUDE.md) AI 交互范式）：

- **自动路径**：检测任务尾部对 top-N 批量归因，LLM 结构化输出 `category + summary`，summary 回写检测行归因字段。
- **手动路径**：页面「AI 归因」按钮 → `useAssistantStore.sendQuestion()` → 助手 agent 按 SKILL.md 取证分析 → persist 工具（`persist_sector_anomaly_attribution` / `persist_stock_anomaly_attribution`）写库并返回 `__event__`（`page_event("sector_anomaly.complete" / "stock_anomaly.complete")`）→ SSE 回写前端刷新。
- **证据工具**：资讯查询（电报 / 新闻文档）、公告、龙虎榜、资金流（个股 / 板块主力净流入）只读查询——证据仅用于归因文本引用。
- SKILL.md 的 allowed-tools 列两条路径工具并集（含 persist 工具与证据查询工具）；结构化输出 schema 字段不带默认值。

## 7. 数据模型

### 7.1 market_anomaly_sector（板块异动日表）

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
| strength | INT NOT NULL | 强度 0-100 |
| attribution_category | VARCHAR(20) | resonance / rotation（归因后回填，可空） |
| attribution_summary | TEXT | 归因摘要（可空） |

约束：`uq_market_anomaly_sector(trade_date, sector_type, sector_code)`；审计字段 `created_at / updated_at`。

### 7.2 market_anomaly_stock（个股异动日表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL pk | |
| trade_date | DATE NOT NULL | 交易日 |
| stock_code / stock_name | VARCHAR | 标的标识与名称 |
| close | NUMERIC(12,4) | 收盘价 |
| change_pct | NUMERIC(8,4) | 当日涨跌幅 % |
| turnover_rate | NUMERIC(8,4) | 换手率 % |
| volume_ratio | NUMERIC(8,2) | 量比（当日量 / 5 日均量） |
| ma60 | NUMERIC(12,4) | 当日 MA60 值 |
| is_above_ma60 | BOOLEAN DEFAULT FALSE | 收盘是否站上 MA60 |
| ma60_breakout | BOOLEAN DEFAULT FALSE | 当日是否有效突破 M60 |
| anomaly_types | JSONB `'[]'` | 命中维度列表 |
| strength | INT NOT NULL | 强度 0-100 |
| attribution_category | VARCHAR(20) | breakout / acceleration / pullback（可空） |
| attribution_summary | TEXT | 归因摘要（可空） |

约束：`uq_market_anomaly_stock(trade_date, stock_code)`；审计字段同上。

## 8. 前端页面

- `/anomaly/sector`（板块异动）与 `/anomaly/stock`（个股异动）双页，挂导航「分析」分组。
- 页面结构：交易日切换 + 异动榜表格（`strength` 排序、`anomaly_types` 筛选、分类徽标）+ 归因摘要列 + 行内「AI 归因」按钮（侧边栏手动重分析）；命中自选股的标的做关联标注。
- 衔接跳转：个股异动行点击直达个股详情；板块命中已建产业链图谱的行业时提供产业链全景直达链接（衔接 F-AI-01）。
- wire 走 camelCase（`CamelModel` + `shared/types` 单一真相源）；事件订阅走 `pageEvents.ts` 注册表 + `usePageAssistantResult`。

## 9. 后续文档索引

- [01-data-source.md](./01-data-source.md) — 数据源（全市场快照 / 新浪日 K / 板块快照）
- [02-data-collection.md](./02-data-collection.md) — 采集引擎与定时任务范式
- [03-data-storage.md](./03-data-storage.md) — 命名约定与 `ai_analysis_result` 缓存
- [04-ai-agent.md](./04-ai-agent.md) — Skill 体系与侧边栏 Agent
- [05-web-frontend.md](./05-web-frontend.md) — 前端架构与页面范式
