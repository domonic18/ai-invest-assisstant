# 08 · 港股支持需求调研

> 状态：P0 已交付（主数据 / 日 K / 快照 / 自选 / 搜索 / 交易日历 / 复盘卡）；P1/P2 待排期（迭代 27）
> 日期：2026-10-19 调研定稿 · 2026-10-30 状态校正
>
> 需求：① 系统目前不支持港股（无港股主数据与行情数据）；② 调研港股数据源，使现有功能尽可能支持港股。

---

## 1. 结论速览

1. **数据可解决**：免费源即可覆盖港股日 K / 快照 / 板块 / 列表主数据（东财 secid=116 体系与现有采集器同族，接入成本最低），但**免费港股行情一律延时 15 分钟**（与 A 股"免费即实时"本质不同）；要实时需付费订阅（LongPort LV1）或券商账户权限（富途）。
2. **部分功能无法平移**：港股**无涨跌停板**，涨停复盘 / 连板天梯 / 涨停池 / 情绪温度 / 风控涨跌停规则对港股不适用，属"功能降级/隐藏"而非移植；掘金仿真**明确不支持港股**，模拟交易需换柜台或本期不做。
3. **改动面**：约 10 处代码格式路由 + 8 处前端 `\d{6}` 正则属机械改动；交易时段、交易日历、涨跌停体系三处是结构性改动，需要参数化设计。
4. **建议分期**：P0 主数据+日K+自选+搜索（底座）→ P1 快照/资金流/复盘扩展 → P2 异动检测与 Agent（模拟交易不做）。P0 即可让"看港股"跑通。

---

## 2. 现状盘点：系统 A 股假设分布

### 2.1 数据源适配层（backend/collector/）

当前 8 类采集任务（specs/：kline、market、pool、fund_flow、news、fundamental、trading）全部围绕 A 股。关键格式路由：

| 位置 | 假设 |
|---|---|
| `collector/core/parsing.py:83-89` | `clean_stock_code` 仅剥 `sh/sz/bj` 前缀 |
| `collector/spiders/sina_kline.py:74-76`（sina_auction/sina_snapshot 同款） | `prefix = "sh" if code.startswith("6") else "sz"` |
| `collector/spiders/stock_minute_base.py:22-28` | 6→sh、0/3→sz，其余返回 None |
| `collector/spiders/tushare_stock_basic.py:19` | `.SH/.SZ/.BJ` 后缀映射 |
| `collector/spiders/eastmoney_sector_fund_flow.py:117` | 板块 secid=`90.{code}` |
| `collector/spiders/tracked_a_share.py:19,37` | ETF 正则 + `market_category=="A股"` 硬过滤 |

**既有港股痕迹**：仅指数级——`app/core/constants.py:52-53` 已含 HSI/HSTECH（东财 secid `100.HSI`/`124.HSTECH`），宏观指数页可展示恒生系。全仓无个股港股代码路径（无 rt_hk/r_hk/116.secid）。

### 2.2 主数据模型

- `StockBasic.stock_code String(10)` + `market String(4)`（sh/sz/bj），唯一约束 `(stock_code, market)`——**模型层天然可容纳 hk**，无需改表
- `UserWatchlist.stock_code String(10)` 无 market 列：同名代码跨市场会歧义（0005.MF 与 00005.HK 不同类，但腾讯 00700 与 A 股无冲突；风险低但建议加列或代码带前缀）
- 搜索接口 `api/v1/stocks.py:29-51` 已有可选 `market` 参数，扩展点现成

### 2.3 功能级假设（结构性差异部分）

| 功能 | A 股假设 | 港股现实 | 处置建议 |
|---|---|---|---|
| 涨停复盘/连板天梯/涨停池 | 东财涨停池接口、±10/20% 封板判定 | **无涨跌停板** | 港股不适用，隐藏；替代：涨幅榜/异动榜 |
| 情绪温度/涨跌统计 | `sina_market_breadth.py:29-37` 阈值表 | 全市场 breadth 口径不同 | 港股另算或隐藏 |
| 集合竞价 | 9:15-9:25 撮合（auction_base.py:32） | 开市竞价 09:00-09:22、收市竞价 16:00-16:08± | 港股隐藏或按 CAS 重做 |
| 风控（paper-trade） | `risk_control.py:76-108` 涨跌停价/ST 禁买/T+1 | 无涨跌停、T+0、无 ST 概念 | 港股分支：无涨跌停校验、T+0 可卖 |
| 交易时段 | `clock.py:24-31`、`intraday.py:62-81`、`tradingRules.ts:34-45` 三处独立硬编码 9:30-15:00 | 09:30-12:00 / 13:00-16:00（HKT） | 参数化 per-market session |
| 交易日历 | akshare A 股日历单源（calendar.py:14-18） | 港股假期不同 | 日历加 market 维度或双源 |
| 异动监测 | 阈值 6%/8%/2.5 倍量 | T+0 波动语义不同 | 港股独立阈值组 |
| 每股交易单位 | 整手 100 股 | 每手股数各异（board lot） | 主数据加 lot_size |
| 两市成交额 | 上交所+深交所官方接口 | 港交所口径 | 港股成交额单独卡 |

### 2.4 前端假设（机械改动）

`\d{6}` 校验共 8 处：`TradingPanel.tsx:94`、`PaperTradePositions.tsx:23`、`usePaperTrade.ts:213`、`StockChartArea.tsx:39`、`orderForm.ts:18`、`pageContext.ts:28,34`、`eventMeta.ts:16`；另 `IndexStrip.tsx:40` 分组、`timeAxis.ts:31-35` 时间刻度。港股代码 5 位数字，建议统一内部表示为 `hk` market + 5 位码。

---

## 3. 港股数据源调研

### 3.1 对比矩阵

| 数据源 | 港股覆盖 | 时效 | 成本 | 接入成本（对本系统） | 备注 |
|---|---|---|---|---|---|
| **东方财富 push2**（akshare `stock_hk_hist` 等同源） | 日 K、实时快照（延 15min）、港股行业板块、板块资金流、港股通成分、股票列表（`fs=m:116`） | 延时 15min | 免费 | **低**：现有 eastmoney spider 同族，secid 前缀 116 | ⭐ 推荐主力 |
| **新浪** `hq.sinajs.cn/list=rt_hkXXXXX` | 实时快照（五档盘口）、全量列表（`stock_hk_spot`，99 页 34s 慢） | 延时 15min | 免费（真实时需购"港股直通卡"） | 低：已有 sina spider 模式；需 Referer 头 + 限速 | 辅助快照源 |
| **腾讯** `qt.gtimg.cn/q=r_hkXXXXX` | 实时快照、分钟线 | 延时 ~15min | 免费 | 低（GBK 文本解析） | 辅助/分钟线 |
| **Yahoo Finance** `.HK` | 日 K | EOD | 免费 | **已有采集器**（注意对出口 IP 小时级 429） | 备份源 |
| **akshare 聚合** | 上述东财/新浪的封装 | 同源 | 免费 | 已是依赖 | 直接用 |
| **Tushare** `hk_basic`/`hk_daily`/分钟 | 列表/日K/分钟/财报 | EOD | 2000 积分起 + **港股行情需单独开权限** | 中 | 备选，暂无必要 |
| **LongPort 长桥 OpenAPI** | LV1/LV2 + WebSocket 推送 | 免费档延 15min；**LV1 实时需订阅付费**（OpenAPI 权限独立于 App） | 接口免费、行情订阅收费 | 中：官方 Python SDK + WebSocket，调用无限 | 实时升级路径 |
| **富途 OpenAPI** | 全品类，SF 高级行情 | 实时（部分权限需资产门槛），历史 K 有 quota | 免费 + quota，需 FutuOpenD 网关（可 Docker 化） | 中高：多一个 Java 网关进程 | 备选 |
| **HKEX 港交所官网** | 日度全量行情文件 | EOD | 免费 | 高（文件解析） | 不推荐 |

### 3.2 关键事实

1. **免费港股行情延时 15 分钟是行业默认**（港交所 LV1 实时授权费所致），东财/新浪/腾讯免费口径一致。对"看行情、复盘、K 线"无感；对"盘中异动监测、集合竞价"体验有损。
2. 东财 `push2` secid 约定：`0.`=深、`1.`=沪、`116.`=港股、`90.`=板块（现有代码已用 0/1/90，加 116 是同族扩展）；港股市场筛选 `fs=m:116`。
3. 财联社电报（已有）本身就覆盖港股资讯，**新闻侧零改动**。
4. 掘金官方 FAQ 明确：**不支持港股/美股交易**，仿真柜台仅沪深 A 股 + 国内期货 → 模拟交易港股必须换方案（自建轻量撮合 / LongPort 模拟交易 / 富途模拟）。

---

## 4. 方案建议（分期）

### P0 · 行情底座（建议先做，1~2 周量级）

- 主数据：港股全量列表采集（东财 `fs=m:116`，含 lot_size 中文名），`stock_basic.market='hk'`；搜索接口/前端联想带出港股
- 日 K：东财 116 secid 日线采集，**前复权**（`adjust="qfq"`）；复用现有 kline spec 骨架，新增 `sina_kline` 的 hk 分支或独立 `eastmoney_hk_kline` spider
- 自选股：watchlist 支持 hk（加 market 列）
- 个股详情页 / K 线 API：代码格式放宽（`hk` + 5 位），周期沿用日/周/月
- 宏观指数：恒生指数/恒生科技**已有**（constants.py），补国企指数等按需
- 交易日历：引入港交所假期表（一年一更，低频 seed）
- 前端：8 处 `\d{6}` 正则放宽 + IndexStrip 港股 tab

### P1 · 盘中与资金面

- 实时快照：新浪 rt_hk / 腾讯 r_hk（延时 15min，UI 明示"延时行情"）；个股分钟线（腾讯）
- 板块：东财港股行业板块 + 板块资金流（secid 体系内扩展）
- 个股资金流、两市量能卡增加"港股成交额"
- 每日复盘：加恒生系指数卡 + 港股涨幅榜（替代涨停口径）

### P2 · 盘中扩展与 Agent（模拟交易不做，已决策）

- **异动监测港股支持**（用户重点）：个股/板块异动检测纳入港股，独立阈值组（T+0 无涨跌停语义，6%/8% 阈值需重校准），基于 15 分钟延时快照可运行
- 交易时段参数化：`clock.py`/`intraday.py` 改 per-market session 表（港股 09:30-12:00/13:00-16:00 HKT，采集调度依赖）
- 交易 Agent 股票池纳入港股（候选池来源改为"涨幅榜∪异动∪持仓"的市场化版本）
- 实时行情升级（可选，远期）：LongPort LV1 订阅或富途 OpenAPI

### 明确不做 / 降级

- 模拟交易港股：**不做**（决策 #3）
- 涨停池、连板天梯、集合竞价页、情绪温度：对港股隐藏（无对应业务语义）
- 付费实时行情：不引入（决策 #2）
- A 股现有功能零回归

---

## 5. 决策记录（2026-10-19 已确认）

1. **标的范围**：按全市场采集（东财 `fs=m:116` 全量），自然覆盖腾讯控股 00700、阿里巴巴 09988 等大盘/港股通标的；后续若要收紧为港股通口径，仅是采集范围过滤，不影响架构
2. **实时性**：15 分钟延时**可接受**。用户以中长期为主，重点是**复盘与异动检测**，不引入付费实时行情
3. **模拟交易**：港股**不做**（掘金不支持，且无需求）；P2 中交易时段参数化仍保留（异动检测/采集调度依赖正确时段）
4. **复权口径**：日 K 需**前复权**（东财 `stock_hk_hist` 原生支持 `adjust="qfq"`，与 A 股 `stock_zh_a_hist` 同参数）
5. **币种**：按同花顺口径——行情/主数据存**港币原价**展示，涉及与 A 股对比的复盘场景按汇率换算（汇率源可用现有宏观指标采集）

---

## 6. 参考来源

- [AKShare 股票数据文档](https://akshare.akfamily.xyz/data/stock/stock.html)（`stock_hk_spot`=新浪 / `stock_hk_hist`=东财）
- [富途 OpenAPI 权限与额度](https://openapi.futunn.com/futu-api-doc/intro/authority.html) / [富途开放接口官网](https://www.futunn.com/OpenAPI)
- [Tushare 港股列表 hk_basic](https://tushare.pro/document/2?doc_id=191) / [港股日线 hk_daily](https://tushare.pro/document/2?doc_id=192)
- [LongPort 定价](https://open.longbridge.com/zh-CN/pricing) / [行情接口概览](https://open.longbridge.com/zh-CN/docs/quote/overview)（OpenAPI 行情权限独立于 App）
- [东方财富港股行情（延时说明）](https://wap.eastmoney.com/quote/hk.html)
- [掘金量化 FAQ（不支持港股/美股交易）](https://www.myquant.cn/docs2/docs) / [仿真文档](https://github.com/myquant/paper-trading-doc)
- 新浪接口 Referer/403：[cnblogs](https://www.cnblogs.com/zeroes/p/sina_stock_api.html)、[leek-fund #359](https://github.com/LeekHub/leek-fund/issues/359)；腾讯接口格式：[cnblogs 解析](https://www.cnblogs.com/soarowl/p/20523904)
