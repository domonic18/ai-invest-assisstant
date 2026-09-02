# 功能开发计划（基于 2026-09-02 实现现状重新评估）

> 需求基准见 [01-requirement.md §7 版本规划](../requirement/01-requirement.md)；部署架构终态见
> [../arch/06-deployment.md](../arch/06-deployment.md)。本文档是功能开发的真相源：
> 维护批次、优先级与状态，每批次落地后更新状态标注。评估基线：2026-09-02（PR #6 已含 web-api 单进程改造）。

## 1. 现状盘点

### 1.1 已落地

| 领域 | 内容 | 佐证 |
|------|------|------|
| 数据采集 | TASK_SPECS 30 任务：行情/ETF/A50、竞价、资金流、新闻、股池（涨停/跌停/炸板）、龙虎榜、研报、财报、IPO、宏观、指数多源 | `collector/runtime/registry.py` |
| AI 定时分析 | 大盘复盘 + 涨停 AI 归因已定时化（交易日 16:30，heavy 队列，input_hash 缓存）| `03-seed.sql` cron `30 16 * * 1-5` |
| 产业链 | 图谱分析 + 版本管理 + 版本对比（手动触发） | `api/v1/chain.py` |
| 前端页面 | 复盘/产业链/个股/热点/资金流/竞价/研报/财报/财务 + 后台管理 9 页（含采集任务目录、LLM 配置） | `web/src/router.tsx` |
| 部署 | SCF + 轻量双节点、CI/CD（TCR）、冷启动 502 已根治 | [../arch/06-deployment.md](../arch/06-deployment.md) |

### 1.2 未落地（按需求编号）

| 需求 | 状态 | 关键缺口 / 前置 |
|------|------|----------------|
| F-DC-04 电报准实时 | 已实现（批次 A） | `cls_telegraph` spider + `collector-stream` 驻留进程（10s 轮询/Redis 游标心跳/指数退避/补漏）；查询 API 待批次 C 工作台定形 |
| F-DC-05 投资日历底座 | 已实现（批次 A） | `calendar_event` 表 + FOMC/BLS 2026 官方日程种子 + 查询 API（CN 日界→UTC 区间）；cls investkalendar 仍留调研项 |
| F-DC-06 全球指标采集 | 已实现（批次 A） | `global-index` 任务（东财 push2delay 实时 + tushare us_tycr 全历史）→ `quote_global_index_daily` |
| F-VIS-07 投资日历页 | 已实现（批次 A） | 月/周/列表三视图 + 分类筛选 + 事件 Drawer，`/calendar` 主导航 |
| F-VIS-08 跟踪指数管理 | 已实现（批次 A） | `tracked_index_config` + Admin 第 10 页 CRUD/启停（无数据源指标禁用启用） |
| F-USER-01 自选股分组 | 未实现 | `user_watchlist` 仅 user_id/stock_code/tags，需分组表改造（单一归属 + AI 复盘开关 + 默认分组） |
| F-AI-07 自选股 AI 每日分析 | 未实现 | 依赖分组开关；**实现路径已有成熟模板**（镜像 market-daily-review 四件套：spider 覆写 run + TaskSpec + seed + heavy 队列） |
| F-VIS-06 工作台 | 未实现 | 纯聚合层，依赖 F-DC-04/05/06 + F-AI-07 的数据底座；登录默认入口从 `/` 切换 |
| F-USER-03 用户级模型配置 | 部分实现 | 仅管理员全局 llm_config，无 user 维度 |
| F-API-01 API-KEY/MCP | 桩 | `/api/v1/mcp/server.py` 返回空，无 API-KEY 管理 |
| F-AI-01 产业链定时刷新 + AI 提醒 | 部分实现 | 版本管理已有；定时更新任务与提醒面板全缺 |
| 小程序端 | 未启动 | V1.0 目标项，整体后置 |

## 2. 重新评估结论

1. **工作台是纯聚合层，数据底座先行**：F-VIS-06 五个模块（日历摘要/复盘结论/要闻/自选概览/市场快览）分别依赖 F-DC-05、既有 ai-review、F-DC-04、F-AI-07、F-DC-06——先底座后聚合，避免空壳页
2. **自选股 AI 链路是最高确定性批次**：定时化机制、input_hash 缓存、heavy 队列串行均已在复盘/归因验证过，属模式复制而非新架构；且它是工作台"自选股概览"的前置
3. **两条数据源风险线必须先调研再排期**：cls investkalendar 签名（日历）与全球指标渠道权限（F-DC-06）——调研不过则对应功能降级（日历先上 FOMC/BLS 权威日程，跟踪指数先上 A 股指数动态化）
4. **后置判断**：小程序端、MCP/API-KEY、用户级模型配置、产业链 AI 提醒均移入后置池——当前单用户/少用户阶段收益低；产业链定时刷新保留在 V1.1 意义上，但优先级低于 V1.2 数据底座
5. **PG 备份入 COS** 维持"排在全部开发计划之后"

## 3. 批次计划

### 批次 A：数据底座（三线可并行）

| 项 | 内容 | 关键落点 | 风险 |
|----|------|----------|------|
| A1 财联社电报采集 | telegraph spider（10s 增量轮询、cls 消息 id 幂等、游标断点）+ 驻留进程部署形态（轻量服务器常驻或 celery beat 短周期） | `collector/spiders/`、`03-seed.sql` | 中：WAF 风控节奏需实测 |
| A2 全球指标 + 跟踪指数管理 | 指标 spider（先验证 tushare us_tycr / 东财 push2delay）→ `quote_global_index_daily` + `tracked_index_config` → Admin 第 10 页 CRUD + 启停校验 | `collector/spiders/`、`models/`、`api/v1/admin/`、`web/src/pages/Admin/` | 中：渠道权限未验证 |
| A3 投资日历底座 | 调研 cls investkalendar 签名（**先调研出结论再排实现**）；无障碍部分先行：`invest_calendar_event` 表 + FOMC/BLS 年度日程半自动导入 + 查询 API | `models/`、`docker/database/migrations/`、`api/v1/` | 高（cls 线）/ 低（FOMC 线） |

> **调研结论回填（2026-09-02 探针实测，批次 A 开发前置项已全部闭环）**
>
> - **A1 cls 电报**：站点已迁 Next.js，旧 `nodeapi/telegraphList`、`api/cache` 均失效；真实端点 `GET www.cls.cn/v1/roll/get_roll_list`。签名 = `md5_hex(sha1_hex(参数按 key 升序 k=v& 拼接))`（非社区旧版 `k1v1k2v2` 裸拼接），sv=8.7.9 硬编码于 `_app` bundle 可正则提取；需 curl_cffi Chrome 指纹 + 首次访问 `/telegraph` 取 WAF Cookie，实测 errno=0 通过。`last_time` 向旧翻页（排他），增量= `last_time=0` 取最新 rn 条按 `ctime>游标` 过滤，rn 上限约 20。→ 按原方案实施，stream 默认启用。
> - **A2 全球指标**：tushare `us_tycr` 权限已通（单次调用返回全量历史，列为 `date/y1..y30`，y2/y10 即美债 2Y/10Y 收益率 %，非 ts_code 接口）；东财 push2delay `ulist.np/get` 实时快照可用（secid `101.GC00Y`/`100.UDI`，fltt=2 已缩放），但 push2delay 无日 K；历史回补走 akshare 三路（`futures_foreign_hist`/`index_global_hist_em`/`bond_zh_us_rate`）实测可用。→ 实时走 push2delay、美债走 us_tycr、回补走 akshare，按原方案实施。
> - **A3 日历**：FOMC/BLS 2026 官方日程已从 federalreserve.gov / bls.gov 实抓（BLS 拒直连，经服务端 reader 通道取得）；cls investkalendar 签名机制与电报同源（同一 sign 模块），复用门槛已大幅降低，仍留调研项、本轮不做。

> **实施回填（2026-09-02，批次 A 三线 + 日历页交付，分支 `feat/batch-a-foundation`）**
>
> - **交付**：`20260902_batch_a_foundation` 迁移（4 新表 + 32 条官方日程种子）；`global-index` / `cls-telegraph-backfill` 任务与 `collector-stream` 驻留服务；日历查询 API 与前端页；Admin 跟踪指数第 10 页。E2E 实测：电报回补 20 条幂等重跑零重复；stream 首启看门狗补漏 64 条（覆盖 2.5h 断档）、重启游标自举零重复、SIGTERM 优雅退出；东财黄金/美元指数实测入库。
> - **与原计划的偏差**：① 全球指标未拆 3 个 TaskSpec，收敛为单 `global-index` 任务（东财/tushare 双渠道 fallback），调度节奏仍按 realtime/收盘后/每日三行 `collector_task` 入 beat，与既有"调度在 DB"模型一致；② 日历表定名 `calendar_event`（原计划 `invest_calendar_event`），归入 market 子域；③ 电报不入 ES（采集侧现状零 ES 写入，与 news 一致）。
> - **新探针发现**：tushare `us_tycr` 限频 **1 次/小时**——种子调度 `30 6 * * 2-6` 每日一次安全，但禁止高频手动重跑；渠道 fallback 会把限频异常转为切源并在 `collector_log.error_msg` 留痕，终态仍 success。
> - **口径修正**：`quote_global_index_daily.change_pct` 全表统一为涨跌幅 %——tushare 美债最初写 bp 差（+4bp 会显示成 +4.00%），已改 `(close-prev)/prev` 并清理本地存量。

### 批次 B：自选股 AI 链路（批次 A 无依赖，可提前启动）

| 项 | 内容 | 关键落点 |
|----|------|----------|
| B1 分组模型改造 | `user_watchlist_group` 表 + `user_watchlist.group_id`（单一归属、默认分组不可删）+ 分组 CRUD API | `models/watchlist.py`、`api/v1/users.py`、迁移 SQL |
| B2 分组 UI + AI 复盘开关 | 自选股页分组折叠组织、分组增删改查/排序、分组级 AI 复盘开关 | `web/src/pages/`、shared 类型 |
| B3 AI 每日分析定时任务 | 镜像 market-daily-review 四件套：skill yaml（三段式输出 Pydantic 校验）+ service（input_hash=skill+code+date 缓存）+ spider 覆写 run + TaskSpec（heavy 队列，单股串行）+ seed cron | `app/prompts/skills/`、`app/services/review/`、`collector/spiders/`、`registry.py`、`03-seed.sql` |
| B4 个股详情 AI Tab | 个股详情页新增"AI 每日分析"Tab（盘面解读/操作策略/止损线 + 免责声明） | `web/src/pages/StockDetail/` |

### 批次 C：工作台聚合（依赖 A1/A2/A3(部分)/B3）

| 项 | 内容 | 关键落点 |
|----|------|----------|
| C1 聚合端点 | `/api/v1/workbench`：一次请求聚合五模块数据（各模块独立降级，缺失返回空态不报错） | `api/v1/`、`services/` |
| C2 工作台页面 | `/workbench` 路由 + 五模块卡片（可折叠）+ 登录默认入口从 `/` 切换（每日复盘保留独立页） | `web/src/pages/Workbench/`、`router.tsx` |

### 后置池（不排序，触发条件成熟再评估）

- 产业链图谱定时自动刷新 + AI 提醒面板（F-AI-01 增强）
- API-KEY 管理 + MCP Server 实装（F-API-01）
- 用户级模型配置（F-USER-03）
- 研报 PDF 全文在线阅读、资金流向桑基图（V1.1 遗留）
- 小程序端（Taro）
- PG 备份入 COS（硬性排最后）

## 4. 状态维护

- 每项落地后在本文件标注：`未实现` → `实现中（分支）` → `已完成（日期 + PR）`
- 批次内验收基线：backend `uv run pytest -m unit` + `mypy` + `ruff`；web `typecheck`/`lint`/`test:unit`/`build`；定时类任务按 collector 验收惯例（任务目录 API 可见、collector_log 终态、前端展示）
- 数据源调研项（A1 cls WAF 节奏、A2 渠道权限、A3 cls 签名）结论直接回填本文件对应行
