# 采集健康监测 需求文档

> 版本：V1.0（2026-09-13 定稿）　状态：待排期
> 上位文档：[01-requirement.md](./01-requirement.md)（本文档为其「数据采集域」运维监测能力的专项扩展，编号启用新域 `F-MON`，实施时回填 01 文档功能总览表）
> 原型：[docs/prototypes/collector-monitoring.html](../prototypes/collector-monitoring.html)（2026-09-13 定稿）

## 1. 文档概述

### 1.1 目的

系统由多渠道（sina / eastmoney / ths / tushare / cls / cninfo / yahoo / mof / exchange / cme / internal）采集 49 类数据任务，渠道时好时坏、任务偶发脱期，目前管理员**无法系统性感知**采集健康程度，只能等问题暴露在页面上（数据缺、复盘空）才被动发现。本文档定义一套面向管理员的采集健康监测能力：看得见整体运行状况、看得见单点故障、看得见计划任务是否如期执行。

### 1.2 适用范围

- 面向用户：管理员（后台）
- 覆盖对象：全部 `TASK_SPECS` 任务类型 × 渠道实例、`collector_task` 全部计划任务声明、`collector_log` 运行记录
- 不涉及：数据内容质量校验（字段级对错）、采集代码修复

### 1.3 术语表

| 术语 | 含义 |
|------|------|
| 任务类型（task_type） | `TASK_SPECS` 键，如 `kline`、`index-spot`、`market-daily-review`；`collector_log.task_name` 存此值 |
| 任务实例 | `collector_task` 一行（task_name 实例名 = task_type × source + cron），即"某渠道上的某类任务计划" |
| 渠道（source） | 数据源身份，与 task_type 二元组构成日志身份 `(task_type, source)` |
| 主/备渠道 | `collector_channel_data_type.priority` 决定的 fallback 顺序；全系统仅 4 个 task_type 有备渠道（a50-kline、auction、sector-fund-flow、global-index） |
| 良性跳过（skipped） | 非交易日、数据已生成等正常终态，不计失败 |
| 脱期 | 按 cron 计划应执行（且应成功）而未执行/未成功 |

## 2. 现状梳理（2026-09-13 实证）

### 2.1 渠道 × 数据类型矩阵

| 域 | 任务类型（渠道：★主 / 备） |
|----|--------------------------|
| K线(7) | kline(sina)、watchlist-kline-daily(sina)、index-kline(sina)、etf-kline(sina)、a50-kline(sina★/eastmoney备)、sector-kline(ths)、kline-freshness(internal) |
| 行情(12) | quote(sina)、auction(sina★/ths备)、index-spot(sina)、index-minute(sina)、index-auction(tushare)、stock-minute(sina)、market-breadth(sina)、market-amount(exchange)、sector-quote(eastmoney)、global-index(eastmoney★/tushare/yahoo/mof备)、fed-watch(cme)、macro(sina) |
| 股池(4) | limit-up-pool / limit-down-pool / broken-pool / dragon-list（全 eastmoney） |
| 资金流(2) | fund-flow(eastmoney)、sector-fund-flow(eastmoney★/ths备) |
| 资讯(4) | news(eastmoney+sina)、news-subscription-match(internal)、cls-telegraph-backfill(cls)、cls-investkalendar(cls)；另有电报实时流（驻留进程，Redis 心跳） |
| 基本面(10) | stock-list(sina)、stock-shares(tushare)、financial-statement_em(eastmoney)、concept-constituents(eastmoney)、company-profile / disclosure / financial-report / ipo(cninfo)、fund-holdings(eastmoney)、research-report(eastmoney) |
| AI(9) | market-daily-review、limit-up-ai-review、stock-daily-analysis、chain-refresh、news-score、news-storyline、news-topic、sector-anomaly、stock-anomaly（全 internal，输入就绪型，大量 skipped 属良性） |

### 2.2 调度与日志链路（可监测的既有事实）

- 调度：`CollectorDatabaseScheduler` 按 `collector_task.schedule`（北京时间 cron）生成 beat entry → `runner.run_task` 统一执行并**唯一写入** `collector_log`
- 渠道选择：`collector_channel_data_type`（is_enabled + priority），preferred_source 置首；仅对 **FAILED** 轮换下一渠道，SUCCESS/PARTIAL/SKIPPED 即终态
- 日志状态机：`pending → running → success / partial / failed / skipped`；`error_msg` 截断 4000 字符；`task_run_id` 藏于 `metadata` JSONB（无独立列）
- 索引就绪：`(task_name, started_at)`、`(status, started_at)` 已建，聚合查询无需新索引
- 退避：输入未就绪类（AI 任务）600s × max_retries=3，耗尽进 `collector_dead_letter`
- 现有"监控"仅 `NEWS_CHANNELS` 注册表（3 条资讯渠道：心跳/日志双判定），**无阈值、无通知、不覆盖其余 46 类任务**

### 2.3 实证发现（本地库，近 30 天 20,017 条日志）

这些真实问题即本需求的直接动因，也是验收对照样本：

| # | 发现 | 数据 | 当前状态 |
|---|------|------|----------|
| 1 | 静默死亡任务 | `ths_concept_constituents`（ths）自 07-26 起 **49 天无成功**，`is_active` 仍为 true | 无人知晓，概念成分股停更 |
| 2 | 渠道级故障 | `a50-kline/eastmoney` 连败（`push2his` Max retries，WAF 拦截），30 天成功率仅 23.1%；sina 主渠道健康兜底中 | 仅主渠道顶上，数据未断但备渠道已死 |
| 3 | 备渠道长期失效 | `ths_auction`（备）最近成功 08-31；`concept-constituents` 东财渠道 30 天成功率 64% | 备份形同虚设 |
| 4 | AI 任务产出中断 | `stock_daily_analysis_1640` 最近成功 09-09，其后每日执行均失败/未产出 | 复盘页个股分析缺失 |
| 5 | 高频任务累积失败 | `index-spot/sina` 30 天 1,062 次失败（成功率 83.9%），盘中限流类噪音 | 噪音淹没真实故障信号 |
| 6 | 日志脏数据 | `news-score/unknown` 193 条、`news-subscription-match/unknown` 96 条 source='unknown' | 渠道维度统计失真 |
| 7 | 接口级异常 | `quote/sina` 09-11 15:55 返回 HTML（`Can not decode value '<'`） | 需观察是否趋势性 |

## 3. 用户与场景

| 场景 | 描述 | 频次 |
|------|------|------|
| 盘前巡检 | 开盘前打开健康页，一眼确认：有无进行中故障、昨日计划任务是否全部按期成功、AI 产出是否就绪 | 每交易日 |
| 故障感知 | 渠道被封/接口改版时，希望**当天**就知道，而非数天后从页面缺口反推 | 事件驱动 |
| 备份有效性确认 | 检查备渠道是否真的能顶上（长期无成功的备份 = 无备份） | 每周 |
| 事后追因 | 数据异常时回查：该数据域哪个渠道采的、何时开始失败、错误是什么、影响面多大 | 事件驱动 |
| 配置修正 | 从健康问题一键跳转渠道配置/任务配置/手动补跑，形成处置闭环 | 事件驱动 |

## 4. 健康度模型（设计核心）

### 4.1 判定对象与状态

判定单元 = **任务实例**（task_type × source，含 cron 计划）。状态机：

| 状态 | 判定规则（cron-aware） | 处置导向 |
|------|----------------------|----------|
| `healthy` 绿 | 最近 cron 窗口内 success；或成功率高且无进行中连败 | — |
| `degraded` 黄 | 仍偶有成功但：7 天成功率 < 阈值（默认 90%）／进行中连败 < 阈值（默认 3 次）／**该实例为主渠道且备渠道已顶上**（数据未断、渠道降级） | 观察、择机修复 |
| `critical` 红 | 按 cron 本应成功而**连续 ≥2 个计划窗口**无 success；或该 task_type 的**全部渠道**均无 success（数据断供） | 立即处置 |
| `silent` 红 | `is_active=true` 且超长无成功（默认 >7 天），含"从未成功过"的新任务配置错误 | 立即处置 |
| `paused` 灰 | `is_active=false`；不参与健康统计与告警 | — |

豁免规则：

- `skipped` 为良性终态：不计入失败率、不打断 healthy 判定（AI 任务的"输入未就绪退避中"属此类）；但**连续 skipped 超过 3 个计划窗口且产生过历史成功**的，降级为 `degraded` 提示（产出停滞预警）
- 非交易日/节假日：计划窗口按交易日历展开，休市日不产生"应跑未跑"
- 高频任务（分钟级）失败属噪音高发区：以**当日成功率**为主要指标（<80% 才 degraded），单次失败不出状态

### 4.2 指标口径

| 指标 | 口径 |
|------|------|
| 成功率 | success / (success+failed+partial)，分 24h / 7d 两窗口；skipped 剔除 |
| 连败 | 自最近一次 success 起连续 failed/partial 次数 |
| 距最近成功 | now − max(success.started_at)，展示按 cron 语义换算（"3 个计划窗口"） |
| 脱期场次 | 观察窗内应执行场次中，无执行记录或无 success 的场次（计划核对表） |
| 入库量 | `records_count`，按 task_type 日汇总；较 7 日均值跌 >70% 判"疑似空采"（P2，先出数不告警） |
| 健康分 | active 实例中 healthy 占比；按数据域分面板呈现 |

### 4.3 错误归因分类（启发式，辅助定位）

从 `error_msg` 模式匹配归为：`WAF/反爬`（HTML 返回、403、Max retries+push2 等特征）、`网络/超时`（ConnectionPool、Timeout）、`接口变更/解析失败`（KeyError、decode、can not decode）、`认证/配额`（api key、token、401/429）、`任务超时`（SoftTimeLimit）、`输入未就绪`（NotReadyError）、`其他`。渠道视图按此聚合，回答"是新浪限流还是东财封禁还是 akshare 改版"。

## 5. 功能需求

### 5.1 F-MON-01 采集健康总览

- **描述**：后台「采集健康」页顶部仪表盘。整体健康分 + 关键计数（进行中故障 / 脱期任务 / 静默任务 / 24h 成功率），按数据域（K线/行情/股池/资金流/资讯/基本面/AI）分组的健康概览
- **关键规则**：有 `critical/silent` 存在时页面顶部常驻告警条（不做弹窗打扰）；观察窗切换 24h / 7d / 30d
- **数据**：聚合 API（见 5.6），实时计算
- **原型**：`collector-monitoring.html` 区块 ①

### 5.2 F-MON-02 任务 × 渠道健康明细

- **描述**：以数据域分组的明细表，每行一个任务实例：任务类型 / 渠道 / 主备角色 / 状态 / 24h·7d 成功率 / 连败 / 距最近成功 / 最近错误摘要（tooltip 全文）/ 操作
- **操作**：查看执行日志（跳转采集日志 Tab 并过滤该 `(task_type, source)`）、手动补跑（复用既有 run 端点）、渠道调试（复用 ChannelDebugModal）、渠道配置（跳转渠道优先级 Tab）
- **排序**：critical/silent > degraded > healthy/paused；支持按数据域、状态过滤
- **原型**：`collector-monitoring.html` 区块 ③

### 5.3 F-MON-03 计划任务执行核对

- **描述**：回答"计划任务是否如期执行、是否按实际情况执行"。按 `collector_task` 声明逐实例核对观察窗内**应执行场次 vs 实际结果**：按期成功 / 执行但失败 / 应跑未跑 / 良性豁免（非交易日、skipped）
- **关键规则**：场次展开用 croniter 按北京时间 + 交易日历；`is_active=true` 但长期无成功的实例在此视图显著标红（静默死亡检测，实证发现 #1 的直接对策）
- **原型**：`collector-monitoring.html` 区块 ⑤

### 5.4 F-MON-04 渠道健康视图

- **描述**：以渠道（source）聚合的反向视角：每个渠道支撑的数据域数、任务实例数、7d 成功率、故障实例数、错误归因分布（4.3 分类）、渠道总开关状态
- **价值**：单渠道故障（如东财 WAF 升级）时，一眼看到受影响面；备份有效性核查（实证发现 #2/#3）
- **原型**：`collector-monitoring.html` 区块 ④

### 5.5 F-MON-05 告警规则与通知

- **描述**：状态进入 `critical/silent` 自动生成告警；`degraded` 不告警（仅页面呈现，避免高频任务噪音）。告警生命周期 `open → acknowledged（认领）→ resolved（恢复自动判定 + 手动确认）`，同一实例未 resolved 前不重复生成（状态升级时更新原告警）
- **阈值可配**：连败阈值、成功率阈值、脱期宽限系数、静默天数（管理端设置，默认值见 4.1）
- **通知**：一期站内（后台入口角标 + 告警中心）；二期可选 Webhook 外发（企业微信/钉钉/Telegram，格式含实例、状态、错误样本、影响数据域、跳转链接）
- **验收注**：阈值变更不重启生效

### 5.6 F-MON-06 健康聚合服务与 API

- **描述**：新增 `services/collector/health_service.py` 与只读聚合端点（admin 权限）。判定器复用并推广 `NEWS_CHANNELS` 的两类 cron 判定思想（轮询型 K×最大间隔 / 批次型计划时刻+宽限），覆盖全量任务实例
- **数据**：全部由 `collector_log` / `collector_task` / `collector_channel_data_type` 派生，**零新表**；告警中心二期引入 `collector_alert` 表
- **性能**：当前库量级（月 ~2 万条日志）单次聚合 < 500ms；预留物化快照升级位
- **约定**：渠道身份一律 `(task_type, source)` 二元组；`collector_log.task_name` 不与 `collector_task.task_name` 实例名联接

### 5.7 F-MON-07 入库量趋势（P2）

- **描述**：task_type 日入库量时序与 7 日均值对比，标记"疑似空采"（成功率正常但 records_count 骤降——捕捉"假成功"）；一期仅在明细表提供最近入库数列

### 5.8 F-MON-08 日志卫生治理（P1，伴随项）

- **描述**：清理 `source='unknown'` 脏日志的写入源头（实证 #6）；`task_run_id` 从 metadata JSONB 提升为独立列（迁移按幂等 SQL 规范）；本文档不展开，实施时单列任务

## 6. 非功能需求

| 项 | 要求 |
|----|------|
| 权限 | 全部端点 admin 角色；健康页仅管理员可见 |
| 时区 | 判定与展示一律北京时间（复用 `app.core.clock`；croniter 按 Asia/Shanghai 展开） |
| 性能 | 总览页首屏 ≤1s；聚合接口 ≤500ms；日志明细走既有分页 |
| 可用性 | 监测只读不侵入采集链路；健康服务异常不得影响采集与业务页面 |
| 治理 | 高频任务噪音抑制（4.1 豁免规则）为一等设计目标，防止"狼来了" |

## 7. 功能边界

**包含**：健康判定/展示/告警（站内）/处置跳转闭环
**不包含**：渠道自动切换（继续人工改 priority）、自动重试策略调整、字段级数据质量校验、告警外发通道的运维（二期仅提供 Webhook 出口）、跨机部署监控（单机栈）

## 8. 分期建议（排期归 development-plan）

| 期 | 内容 | 特征 |
|----|------|------|
| 一期 | F-MON-01/02/03/04/06（健康服务 + 总览/明细/核对/渠道视图 + 站内角标） | 零新表、纯只读聚合，最快见效 |
| 二期 | F-MON-05 完整告警（collector_alert 表 + 认领流 + 阈值配置）+ Webhook 外发 | 引入新表与迁移 |
| 后置 | F-MON-07 量趋势告警、F-MON-08 日志卫生、快照物化 | 触发条件立项 |

## 9. 验收对照（用实证样本验收）

| 样本 | 预期呈现 |
|------|----------|
| ths_concept_constituents | `silent` 红色 + 告警"49 天无成功" |
| a50-kline/eastmoney | `degraded`（主渠道 sina 顶上，备渠道连败 3 次）+ 渠道视图 eastmoney 归因 WAF |
| stock_daily_analysis_1640 | `critical`（连续 3 个交易日窗口无 success） |
| index-spot/sina | 24h 成功率口径下 healthy（噪音豁免），30d 视图可见 83.9% |
| news-score/unknown | 不参与健康统计（治理项单列） |
| 周末打开页面 | 交易日历豁免，无"应跑未跑"误报 |
