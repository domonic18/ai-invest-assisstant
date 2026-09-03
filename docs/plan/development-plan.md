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
| F-DC-04 电报准实时 | 已实现（批次 A） | `cls_telegraph` spider + `collector-stream` 驻留进程（10s 轮询/Redis 游标心跳/指数退避/补漏）；分页查询 API + `/telegraph` 时间线页（10s 自动刷新/新电报红点/断流延迟探针） |
| F-DC-05 投资日历底座 | 已实现（批次 A + investkalendar 增补） | `calendar_event` 表 + FOMC/BLS 2026 官方日程种子 + cls investkalendar 每日采集（2026-09-03）+ 查询 API（CN 日界→UTC 区间） |
| F-DC-06 全球指标采集 | 已实现（批次 A） | `global-index` 任务（东财 push2delay 实时 + tushare us_tycr 全历史）→ `quote_global_index_daily` |
| F-VIS-07 投资日历页 | 已实现（批次 A） | 月/周/列表三视图 + 分类筛选 + 事件 Drawer，`/calendar` 主导航 |
| F-VIS-08 跟踪指数管理 | 已实现（批次 A） | `tracked_index_config` + Admin 第 10 页 CRUD/启停（无数据源指标禁用启用） |
| F-USER-01 自选股分组 | 已实现（批次 B） | `user_watchlist_group` + `group_id` 单一归属（默认分组不可删，非默认组删除时股票移入默认组）+ 分组 CRUD/排序 API + `/watchlist` 管理页与分组级 AI 开关 |
| F-AI-07 自选股 AI 每日分析 | 已实现（批次 B） | `stock-daily-analysis` 四件套（heavy 队列单股串行、input_hash 缓存、K 线缺失降级）+ `GET /stocks/{code}/ai-analysis` + StockDetail "AI 分析" Tab |
| F-VIS-06 工作台 | 已实现（批次 C） | `GET /api/v1/workbench` 七模块聚合（整端点鉴权、逐模块降级恒 200）+ `/workbench` 五卡片页；登录默认入口 `/` → `/workbench`，每日复盘迁 `/review` |
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

> **增补回填（2026-09-03，cls investkalendar 采集上线，分支 `feat/cls-investkalendar`）**
>
> - **调研结论（探针实测，原 A3 留调研项闭环）**：旧 `nodeapi/updateInvestkalendar` 已 404；真实端点 `GET www.cls.cn/api/calendar/web/list`（由页面 chunk `pages/investkalendar-*.js` 定位），签名与电报同源（`cls_sign` 复用）。端点固定返回**今日起约 3 周滚动前瞻窗口**（`tradeDate` 不改变窗口），每日一次全量拉取即可覆盖；条目 `type=1` 经济数据（economic 载荷：前值/预期/公布值/star）→ `宏观`、`type=2` 事件会议 → `会议`；`calendar_time` 为北京时间字符串（00:00:00=时间未定）。新股/解禁为 cls 独立接口，本轮不扩。
> - **交付**：`cls-investkalendar` 任务四件套（spider `cls_investkalendar.py` 复用电报共享 WAF 会话 + TaskSpec + cls 渠道登记 + 迁移 `20260903_cls_investkalendar.sql` 调度 `15 7 * * *` 全周）写入 `calendar_event`（`source_hash=md5(source|event_time|title)` 幂等 DO NOTHING，不追踪 cls 侧预期值/公布值更新）。E2E：CLI 触发 SUCCESS 57 条入库（33 会议 + 24 宏观），北京时间→aware UTC 换算正确，重跑零重复，`/calendar/events` API 与后台任务目录（34 任务）可见。
> - **偏差**：① `impact_markets`/`related_symbols` 不从 cls 数据推导（避免编造口径），留空；② cls 渠道在 `DEFAULT_CHANNELS`/seed 的 `supported_data_types` 同步登记任务名；③ 电报 spider 的 `_get_session` 公开为 `shared_session()` 供两任务复用同一 WAF 会话。

> **实施回填（2026-09-02，批次 A 三线 + 日历页交付，分支 `feat/batch-a-foundation`）**
>
> - **交付**：`20260902_batch_a_foundation` 迁移（4 新表 + 32 条官方日程种子）；`global-index` / `cls-telegraph-backfill` 任务与 `collector-stream` 驻留服务；日历查询 API 与前端页；Admin 跟踪指数第 10 页。E2E 实测：电报回补 20 条幂等重跑零重复；stream 首启看门狗补漏 64 条（覆盖 2.5h 断档）、重启游标自举零重复、SIGTERM 优雅退出；东财黄金/美元指数实测入库。
> - **与原计划的偏差**：① 全球指标未拆 3 个 TaskSpec，收敛为单 `global-index` 任务（东财/tushare 双渠道 fallback），调度节奏仍按 realtime/收盘后/每日三行 `collector_task` 入 beat，与既有"调度在 DB"模型一致；② 日历表定名 `calendar_event`（原计划 `invest_calendar_event`），归入 market 子域；③ 电报不入 ES（采集侧现状零 ES 写入，与 news 一致）。
> - **新探针发现**：tushare `us_tycr` 限频 **1 次/小时**——种子调度 `30 6 * * 2-6` 每日一次安全，但禁止高频手动重跑；渠道 fallback 会把限频异常转为切源并在 `collector_log.error_msg` 留痕，终态仍 success。
> - **口径修正**：`quote_global_index_daily.change_pct` 全表统一为涨跌幅 %——tushare 美债最初写 bp 差（+4bp 会显示成 +4.00%），已改 `(close-prev)/prev` 并清理本地存量。
> - **范围追加**：电报查询 API + `/telegraph` 前端时间线页自批次 C 提前落地（原计划后置到工作台）——采集链路需要可视化验收入口：分页查询（公开路由，镜像 calendar 竖切片）+ 后端一次剥净 cls 富文本 HTML + 10s 自动刷新/新电报 NEW 红点/最新延迟断流探针。

### 批次 B：自选股 AI 链路（批次 A 无依赖，可提前启动）

| 项 | 内容 | 关键落点 |
|----|------|----------|
| B1 分组模型改造 | `user_watchlist_group` 表 + `user_watchlist.group_id`（单一归属、默认分组不可删）+ 分组 CRUD API | `models/watchlist.py`、`api/v1/users.py`、迁移 SQL |
| B2 分组 UI + AI 复盘开关 | 自选股页分组折叠组织、分组增删改查/排序、分组级 AI 复盘开关 | `web/src/pages/`、shared 类型 |
| B3 AI 每日分析定时任务 | 镜像 market-daily-review 四件套：skill yaml（三段式输出 Pydantic 校验）+ service（input_hash=skill+code+date 缓存）+ spider 覆写 run + TaskSpec（heavy 队列，单股串行）+ seed cron | `app/prompts/skills/`、`app/services/review/`、`collector/spiders/`、`registry.py`、`03-seed.sql` |
| B4 个股详情 AI Tab | 个股详情页新增"AI 每日分析"Tab（盘面解读/操作策略/止损线 + 免责声明） | `web/src/pages/StockDetail/` |

> **实施回填（2026-09-02，批次 B 四项交付，分支 `feat/batch-b-watchlist-ai`）**
>
> - **交付**：迁移 `20260902_batch_b1_watchlist_group.sql`（分组表 + `group_id` 回填 + SET NOT NULL，幂等验证两遍）；分组 CRUD/排序/移动/删除 API + `/watchlist` 管理页（分组折叠、AI 开关、跨组移动）；`stock-daily-analysis` 四件套（skill yaml + service + spider + TaskSpec heavy 队列）与查询端点 `GET /stocks/{code}/ai-analysis`；StockDetail "AI 分析" Tab。E2E 实测：本地容器重建后 CLI 触发任务 SUCCESS，两只自选股（桂冠电力/爱丽家居）经 Kimi（anthropic 协议）真实生成，`ai_analysis_result.stock_code` 按股落行、input_hash 含 stock_code 各不相同、4 sections 全非空；查询端点未登录 401 符合预期。
> - **关键修正（渠道登记以任务名为键）**：internal 渠道的 `supported_data_types`、`collector_channel_data_type.data_type`、`collector_task.task_type` 三处都必须登记 TaskSpec **name**（`stock-daily-analysis`）而非 `data_type`（`ai_stock_daily_analysis`）——渠道解析（`resolver.py` 按 `data_type == task_name` 匹配）与 beat 派发（`celery_beat.py` 以 `task_type` 为任务名）都以任务名为键，与 market-daily-review / limit-up-ai-review 既有先例一致；首轮验收曾因误用 data_type 登记 SKIPPED"没有启用任何可用的采集渠道"，已在迁移中含修复块（jsonb 剔除 + 残留行清理）。
> - **与原计划的偏差**：① skill 输出定稿 4 段（盘面解读/关键事件/操作策略/风险与止损，原计划三段式）；② `input_hash` 实为 `sha256(skill_id:section_keys:stock_code:trade_date)`（含 section 键，原计划 skill+code+date）；③ 删除非默认分组时组内股票**移入默认分组**（用户决策，非级联删除）；④ K 线缺失时降级为仅行情生成并在 prompt 注明数据范围，K 线与行情全缺才抛 `ReviewInputDataNotReadyError` 走 celery 10 分钟重试，spider 仅在全部股票未就绪时整体 re-raise，单股失败隔离并回滚。

### 批次 C：工作台聚合（依赖 A1/A2/A3(部分)/B3）

| 项 | 内容 | 关键落点 |
|----|------|----------|
| C1 聚合端点 | `/api/v1/workbench`：一次请求聚合五模块数据（各模块独立降级，缺失返回空态不报错） | `api/v1/`、`services/` |
| C2 工作台页面 | `/workbench` 路由 + 五模块卡片（可折叠）+ 登录默认入口从 `/` 切换（每日复盘保留独立页） | `web/src/pages/Workbench/`、`router.tsx` |

> **实施回填（2026-09-03，批次 C 交付，分支 `feat/batch-c-workbench`）**
>
> - **交付**：`GET /api/v1/workbench`（整端点鉴权）一次聚合七字段——calendar(8)/review/telegraph(12)/watchlist_groups/indices/stats/global_indices，聚合服务顺序 await + 每模块独立 try/except 降级（structlog warning + 空态兜底，整体恒 200）；配套补齐全球指标公开读端点 `GET /api/v1/market/global-indices`（`TrackedIndexConfig` 全球分类按 sort_order → `GlobalIndexDaily` 每 code 最新行，启用过滤）。前端 `/workbench` 按原型（`docs/prototypes/workbench.html`）布局：页首 8 指标横条（A 股跟踪指数 + 全球指标）→ 左列「复盘核心结论（分区摘要 + 情绪 chips）/ 要闻资讯（准实时徽标 + 标签行）/ 自选股概览（分组 chips 切换 + AI 状态与盘面解读摘要 + 免责声明）」右列「投资日历（今日标记）/ 板块资金动向空态卡 / 快捷入口」，全部卡片可折叠；`/` 重定向 `/workbench`、Dashboard 迁 `/review`、登录/注册落 `/workbench`、侧边栏与移动 TabBar 首项工作台、pageContext 增补两路由。
> - **自选概览的聚合扩展（原型反馈驱动）**：`watchlist` 字段升级为 `watchlist_groups`——分组容器（名称/默认/`ai_review_enabled`）+ 行内 `ai_status`（`off` 分组未开启 / `pending` 已开启未生成 / `ready` 已生成）与 `ai_summary`（`intraday_review` 分区剥 Markdown 截 120 字）；`ai_analysis_repository.load_success_by_hashes` 按 input_hash 批量取最新 success 记录，同一行情组装抽出 `_build_quote_items` 复用。`ready` 判定锚定最近交易日，当日 16:30 任务未跑前显示 `pending` 属预期。
> - **与原计划的偏差**：① 聚合并发用顺序 await 而非 `asyncio.gather`——既有 gather 先例（index_quotation_service）共享单个 AsyncSession 属不安全模式，不复刻，七模块全为 Redis/索引 PG 快读顺序总耗时可控；② `review=None`（当日未生成）按正常空态透传，不计入降级日志；③ 首轮实现未对齐原型（指数埋在重型卡、无分组/AI 摘要），已按 `workbench.html` 重构并补折叠（antd 5.29 Card 无 collapsible，自建 FoldCard）；④ Register.tsx 同步登录后跳转（计划只列 Login.tsx）。
> - **验收（API 级已过，浏览器侧待人工）**：backend unit 全绿（global_index 4 例 + workbench service 3 例 + watchlist_groups 4 例 + api 用例更新）/ mypy / ruff；web typecheck/lint/test:unit(85)/build 全绿；docker 重建后 curl 实测：无 token `/workbench` 401、带 token（sub=3）200 七字段齐（`watchlist_groups` 分组/AI 状态正确：未开启组 `off`、开启组盘后前 `pending`）、`/market/global-indices` 无鉴权 200、SPA `/workbench` 与 `/review` 均 200。

### 后置池（不排序，触发条件成熟再评估）

- 产业链图谱定时自动刷新 + AI 提醒面板（F-AI-01 增强）
- API-KEY 管理 + MCP Server 实装（F-API-01）
- 用户级模型配置（F-USER-03）
- 研报 PDF 全文在线阅读、资金流向桑基图（V1.1 遗留）
- 小程序端（Taro）
- PG 备份入 COS（硬性排最后）
- 存储治理三件套（2026-09-02 全库审计发现，上生产前评估）：① 4 张 hypertable 开 TimescaleDB 压缩策略（分钟线收益最大）② collector_log 保留策略（建议 90 天，index-minute/index-spot 占增量约 3/4）③ LangGraph checkpoint 随 assistant_session 删除级联清理（存量约 20 个孤儿 thread）

## 4. 状态维护

- 每项落地后在本文件标注：`未实现` → `实现中（分支）` → `已完成（日期 + PR）`
- 批次内验收基线：backend `uv run pytest -m unit` + `mypy` + `ruff`；web `typecheck`/`lint`/`test:unit`/`build`；定时类任务按 collector 验收惯例（任务目录 API 可见、collector_log 终态、前端展示）
- 数据源调研项（A1 cls WAF 节奏、A2 渠道权限、A3 cls 签名）结论直接回填本文件对应行
