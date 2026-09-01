# 数据源设计

> 任务与渠道的权威目录是 `backend/collector/runtime/registry.py` 的 TASK_SPECS（33 个任务），运行时可经 `GET /api/v1/admin/collector/tasks/catalog` 查询；本文描述各数据源的定位、反爬要点与存储去向。

## 1. 数据源全景

```
┌────────────────────────────────────────────────────────────────────────┐
│                            数据源矩阵                                   │
├──────────────┬──────────────┬──────────────┬───────────────────────────┤
│   新浪财经    │  东方财富     │  巨潮资讯     │  同花顺 / Tushare / 交易所 │
│ finance.sina │ eastmoney    │ cninfo.com.cn│ 10jqka / tushare / sse-sz │
│   .com.cn    │   .com       │              │                           │
├──────────────┼──────────────┼──────────────┼───────────────────────────┤
│ ● K线(个股/  │ ● 涨停/跌停池 │ ● 财报PDF     │ 同花顺：                   │
│   指数/ETF)  │ ● 炸板统计    │ ● 公告披露    │ ● 集合竞价(备选)          │
│ ● 行情/列表  │ ● 龙虎榜     │ ● 公司概况    │ ● 板块资金流(备选)        │
│ ● 涨跌统计   │ ● 资金流向    │ ● IPO 信息    │ Tushare：                 │
│ ● 分钟线     │ ● 概念成分股  │              │ ● 指数集合竞价(唯一)      │
│ ● 新闻/宏观  │ ● 个股研报    │              │ 交易所：                  │
│ ● 集合竞价   │ ● 基金持仓    │              │ ● 市场成交额(唯一)        │
│              │ ● 富时A50     │              │ internal：AI 生成任务     │
│              │ ● 全球指数/黄金│             │ 财联社：电报快讯/日历     │
│              │              │              │ Fed/BLS：固定日程         │
└──────────────┴──────────────┴──────────────┴───────────────────────────┘
```

## 2. 各数据源定位与要点

### 2.1 新浪财经 — 行情主渠道（11 任务）

| 数据类型 | 说明 | 备注 |
|----------|------|------|
| K 线（`kline_{period}`） | 个股日/周/月 K | **唯一 K 线渠道**（同花顺 K 线已下线：其接口实走东财 push2his 路径，已被 WAF 封死） |
| 指数 K 线 / ETF 日 K | `index-kline` / `etf-kline` | |
| 行情快照 / 股票列表 | `quote` / `stock-list` | |
| 涨跌统计 | `market-breadth` | 市场宽度 |
| 指数/个股分钟线 | `index-minute` / `stock-minute` | 分钟线仅盘前竞价与盘中语义，禁用于指数竞价成交额口径（首根 bar 盘后被修订） |
| 新闻 / 宏观经济 | `news` / `macro` | 入 ES 索引 |
| 集合竞价 | `auction`（sina→ths 双渠道） | 个股竞价 |

### 2.2 东方财富 — 股池/资金流/研报（9 任务）

| 数据类型 | 说明 | 备注 |
|----------|------|------|
| 涨停股池 / 跌停股池 / 炸板统计 | `limit-up-pool` / `limit-down-pool` / `broken-pool` | 16:00 批次；为涨停 AI 归因的上游 |
| 龙虎榜 | `dragon-list` | |
| 资金流向 | `fund-flow` | 个股资金流 |
| 板块资金流向 | `sector-fund-flow`（eastmoney→ths 双渠道） | 行业/概念；概念板块口径钉死同花顺语义 |
| 概念成分股 | `concept-constituents` | 高频连发触发 WAF，走 **push2delay 镜像 + curl_cffi** |
| 个股研报 / 基金持仓 | `research-report` / `fund-holdings` | 研报 PDF 下载走 curl_cffi Chrome 指纹（pdf.dfcfw.com 按 TLS 指纹拦截 httpx） |
| 富时 A50 | `a50-kline` | 无替代源 |
| 全球指数 / 黄金 | `global-index`（美元指数 UDI / COMEX 黄金等） | 跟踪指数清单（见 03 §3.9）的数据源主渠道；低频采集走 push2delay，akshare `index_global_*` 可作口径参考 |

**WAF 行为要点**：按 TLS 指纹 + 路径 + 主机限流（非简单 IP 封禁）。`push2` 高频连发按主机封禁→批量拉取用 `push2delay` 镜像；`push2his` kline 路径已封死→K 线一律走新浪。

### 2.3 巨潮资讯 — 信息披露（4 任务）

公司概况 / 公告披露 / 财报（PDF 入 COS，结构化字段入 PG）/ IPO 信息。更新跟随披露节奏（财报季加密扫描）。

### 2.4 同花顺 — 备选渠道（不独立承担任务）

仅作为 `auction`（sina 之后的第二渠道）与 `sector-fund-flow`（eastmoney 之后的第二渠道）的 fallback，不单独注册任务。

### 2.5 Tushare / 交易所 — 口径唯一渠道

| 数据类型 | 来源 | 说明 |
|----------|------|------|
| 指数集合竞价 | Tushare `stk_auction` | 指数竞价成交额**唯一口径**（聚合自个股），竞价付费权限已开通 |
| 市场成交额 | 交易所（`exchange`） | 沪深两所官方口径 |
| 美债收益率（2Y/10Y） | Tushare `us_tycr` | 美债收益率唯一口径；渠道已接，实施前确认积分权限 |

### 2.6 internal — AI 生成任务（非外部采集）

| 任务 | 说明 |
|------|------|
| `market-daily-review` | 每日复盘综述，交易日 15:05 触发，LLM 生成，结果缓存 `ai_analysis_result` |
| `limit-up-ai-review` | 涨停 AI 归因，交易日 16:30 触发（依赖 16:00 涨停股池），同缓存机制 |
| `watchlist-daily-analysis` | 自选股 AI 每日分析，交易日盘后批量（heavy 队列），仅遍历开启 AI 复盘开关的分组；三段式输出（盘面解读/操作策略/止损线），按 skill+code+日期 缓存 |

### 2.7 财联社 — 电报快讯（准实时）+ 投资日历

财联社两类数据共用一套接入机制（开源 cls-monitor 实现验证）：`sign = MD5(SHA1(参数按 key 字母序拼接))` 签名、`curl_cffi` Chrome TLS 指纹、页面预热获取 WAF Cookie、`sv` 版本号从页面 JS bundle 自动提取。

| 数据 | 接口 | 采集方式 | 存储 |
|------|------|----------|------|
| 电报 7×24 快讯 | `www.cls.cn/api/cache`（`name=telegraphList` + `lastTime` 增量游标） | 驻留进程 10 秒增量轮询——官方无推送 API/WebSocket，页面"实时"本身即 10s 轮询，同节奏即准实时且与真实用户行为一致；游标断点续传、失败指数退避、看门狗补漏 | 快讯入 ES 索引，按 cls 消息 id 幂等 |
| 投资日历事件 | investkalendar nodeapi | 每日增量采集 | `calendar_event`，按 `source_hash` 幂等去重 |

日历接口两条落地路径：① 逆向签名机制直连接口；② 兜底解析其每月"资本市场大事提醒"栏目文章。

### 2.8 海外官方 — 固定日程（半自动导入）

| 数据类型 | 来源 | 说明 |
|----------|------|------|
| FOMC 议息会议日程 | federalreserve.gov 年度日历页 | 每年初发布、结构稳定，导入脚本 + 人工校对 |
| 美国 CPI / 非农等披露日程 | bls.gov/schedule | 同上 |
| 平台衍生事件 | 财报披露日期 / AI 提取的关键里程碑 | 自选股财报披露自动关联；AI 从财报提取技术突破等事件时间（见 [04 §8.2](./04-ai-agent.md)） |

## 3. 渠道优先级与故障切换

- 每个 TaskSpec 声明 `collectors = {channel: 采集器}`，渠道按声明顺序即优先级，由 `collector.runtime.resolver` 按渠道配置解析
- **fallback 只对 FAILED 轮换下一渠道**；`SKIPPED`（非交易日、已生成、无数据等）是良性终态，不轮换、不改写为 FAILED
- 全渠道失败 → FAILED + `collector_dead_letter` 死信记录，告警后人工/定时补跑
- 日期类参数默认 `latest_trading_day()`（非 `today_cn()`），避免周末手动补跑静默空采

## 4. 反爬与限流策略（实际实现）

| 策略 | 实现 |
|------|------|
| TLS 指纹伪装 | 东财系接口（概念成分、研报 PDF）用 `curl_cffi` Chrome 指纹，httpx 会被识别返回 JS 反爬页 |
| 镜像域名 | `push2delay` 承接东财批量拉取，规避 `push2` 主机限流 |
| 请求限流 + 退避 | `collector.core.http_client` 统一超时/重试/间隔控制 |
| 固定出口 IP | 采集 worker 永久驻留轻量服务器，固定出口 IP 对东财 WAF 更友好（SCF 共享出口池风险高） |
| 随机 User-Agent | http_client 默认注入 |

> 未采用：IP 代理池、验证码打码、多账号 Cookie 池（无必要，当前量级限流退避即可）。

## 5. 存储去向

| 数据 | 存储 | 说明 |
|------|------|------|
| 行情/K线/股池/资金流/财务结构化字段/调度元数据/全球指标行情 | PostgreSQL + TimescaleDB | 时序表走 hypertable |
| 新闻 / 公告 / 电报快讯全文 | Elasticsearch | 全文检索 |
| 财报 PDF / 研报 PDF | COS（S3 兼容） | 预签名 URL 下载 |
| AI 分析结果（复盘综述/涨停归因/自选股每日分析） | `ai_analysis_result` 表 | 按 `input_hash`（skill_id + 业务键）幂等缓存 |
| 投资日历事件 | `calendar_event` 表 | 按 `source_hash` 幂等去重 |
