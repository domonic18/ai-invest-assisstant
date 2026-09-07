# 功能开发计划（基于 2026-09-02 实现现状重新评估；2026-09-07 增补 V1.3 批次 F-I）

> 需求基准见 [01-requirement.md §7 版本规划](../requirement/01-requirement.md)；部署架构终态见
> [../arch/06-deployment.md](../arch/06-deployment.md)。本文档是功能开发的真相源：
> 维护批次、优先级与状态，每批次落地后更新状态标注。评估基线：2026-09-02（PR #6 已含 web-api 单进程改造）；
> V1.3 批次（F-I）评估基线：2026-09-07（V1.3 原型与需求文档已定稿，见 §1.1）。

## 1. 现状盘点

### 1.1 已落地

| 领域 | 内容 | 佐证 |
|------|------|------|
| 数据采集 | TASK_SPECS 30 任务：行情/ETF/A50、竞价、资金流、新闻、股池（涨停/跌停/炸板）、龙虎榜、研报、财报、IPO、宏观、指数多源 | `collector/runtime/registry.py` |
| AI 定时分析 | 大盘复盘 + 涨停 AI 归因已定时化（交易日 16:30，heavy 队列，input_hash 缓存）| `03-seed.sql` cron `30 16 * * 1-5` |
| 产业链 | 图谱分析 + 版本管理 + 版本对比（手动触发） | `api/v1/chain.py` |
| 前端页面 | 复盘/产业链/个股/热点/资金流/竞价/研报/财报/财务 + 后台管理 9 页（含采集任务目录、LLM 配置） | `web/src/router.tsx` |
| AI 交互范式（批次 E，PR #15-#18） | 页面级 AI 统一走侧边栏助手 + page_event 回写（大盘复盘/个股每日分析/涨停归因 deepagents skill 内核化）；大盘复盘 Admin 页；自选股截图识别导入；K 线新鲜度自愈任务 | `app/agent/tools/page_event.py`、`web/src/components/assistant/pageEvents.ts` |
| 后端工程质量（重构批次 1-7，PR #20-#26） | P0 快赢/安全运行时/后端一致性/数据访问收敛/schema wire/结构前端/**Skill 体系基建**：BUILTIN_SKILLS registry + `skills/<id>/` 资产目录统一 + `skill`/`user_skill` 表 + 广场/安装/custom skill CRUD API + assistant 技能摘要 registry 化 + custom 技能索引注入 | `app/skills/registry.py`、`api/v1/skills.py`、`skills/` |
| V1.3 原型与需求定稿（2026-09-06/07） | 四新页原型（宏观监测/资讯中心/板块异动/个股异动）+ 导航 4.4.0 重组 + 研报/财报并入个股侧栏 + 资讯中心合并热点追踪 + 产业图谱/后台管理/工作台原型对齐实现 | `docs/prototypes/`（18 页零死链）、[01-requirement.md](../requirement/01-requirement.md) |
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
| F-AI-01 产业链定时刷新 + AI 提醒 | 已实现（批次 D） | `chain-refresh` 周任务（周六 06:00 北京时间，heavy 逐链串行，按用户复制落版本）+ `chain_alert` 表（同链同类型同日唯一）+ `GET /chain/alerts` + 图谱页 ChainAlertPanel |
| 导航重组 + 研报/财报侧栏化（4.4.0） | 原型/需求已定稿（2026-09-07），前端未实现 | 侧边栏四分组 12 项；`/research`、`/financial-reports`、`/hotspot` 独立导航移除；研报/财报并入个股详情右栏 tab —— 排批次 F |
| F-VIS-09 宏观指数监测页 | 原型已定稿（`macro-monitor.html`），未实现 | 二批指标源缺：港股/美股指数、日债 10Y、加息概率（CME FedWatch 调研项）—— 排批次 G |
| F-VIS-04 扩展：板块监测页升级 | 原型已定稿（`capital-flow.html` 升级版），未实现 | 缺板块指数行情采集（行业/概念板块涨跌幅 + 成交额）—— 排批次 G |
| F-VIS-10 资讯中心（含 F-AI-03） | 原型已定稿（`news.html`），未实现 | 缺：渠道监控 API / 电报 AI 重要度分级（`importance` 现为 cls 源 level，非 AI）/ 重点与故事线 / 热点主题 / 订阅规则 —— 排批次 H |
| F-AI-09 板块异动分析 | 原型已定稿（`sector-anomaly.html`），未实现 | 检测算子 + AI 归因 + 页面全缺 —— 排批次 I |
| F-AI-10 个股异动分析 | 原型已定稿（`stock-anomaly.html`），未实现 | 检测算子 + AI 归因 + 页面全缺 —— 排批次 I |
| Skill 广场前端（F-USER-04） | 原型已定稿（`skill-square.html`），后端 API 已就绪（批次 7），web 未做 | `/skills` 广场/安装/custom CRUD 端点 + shared 类型已有 —— 排批次 J |
| 小程序端 | 未启动 | V1.0 目标项，整体后置 |

## 2. 重新评估结论

1. **工作台是纯聚合层，数据底座先行**：F-VIS-06 五个模块（日历摘要/复盘结论/要闻/自选概览/市场快览）分别依赖 F-DC-05、既有 ai-review、F-DC-04、F-AI-07、F-DC-06——先底座后聚合，避免空壳页
2. **自选股 AI 链路是最高确定性批次**：定时化机制、input_hash 缓存、heavy 队列串行均已在复盘/归因验证过，属模式复制而非新架构；且它是工作台"自选股概览"的前置
3. **两条数据源风险线必须先调研再排期**：cls investkalendar 签名（日历）与全球指标渠道权限（F-DC-06）——调研不过则对应功能降级（日历先上 FOMC/BLS 权威日程，跟踪指数先上 A 股指数动态化）
4. **后置判断**：小程序端、MCP/API-KEY、用户级模型配置、产业链 AI 提醒均移入后置池——当前单用户/少用户阶段收益低；产业链定时刷新保留在 V1.1 意义上，但优先级低于 V1.2 数据底座
5. **PG 备份入 COS** 维持"排在全部开发计划之后"
6. **V1.3 执行原则（2026-09-07）**：先纯前端快赢（批次 F 导航重组，零后端依赖）兑现原型定稿的信息架构；监测双页（G）数据源调研先行，调研不过则降级（加息概率降级为 FOMC 日历占位）；资讯中心（H）与异动分析（I）相互独立可并行，但 H 先行——异动归因的「关联资讯时间线」复用 H 的查询能力更顺；所有新 AI 能力一律走既有范式（侧边栏触发 + page_event 回写 / 定时 internal 任务，SKILL.md 双路径共用）

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

### 批次 D：产业链 AI 提醒（F-AI-01）+ 存储治理（2026-09-03 立项，分支 `feat/batch-d-chain-alerts`）

> 依赖盘点：V1.2 数据底座（批次 A/B/C）收官后首轮迭代。D1 → D2 串行（告警由刷新任务产出），
> D3/D4 与主线独立可并行。需求基准 [01-requirement.md F-AI-01](../requirement/01-requirement.md)：
> 定时自动更新（每周/每月 AI 重新分析）+ 手动触发（已有 POST /chain/analyze）+ AI 提醒 5 触发类型；
> "重大事件触发刷新"后置池保留。MCP get_chain_alerts 随 F-API-01 后置。

| 项 | 内容 | 关键落点 | 风险 |
|----|------|----------|------|
| D1 产业链定时刷新 | 镜像 market-daily-review 四件套：skill yaml（结构化输出 Pydantic 校验，更新内容=财务数据/核心标的/国产化率/动态事件）+ service（input_hash 缓存防重）+ 覆写 run 的 spider + TaskSpec（heavy 队列，逐链串行）+ seed cron；产物走既有版本管理落新版本 | `app/prompts/skills/`、`app/services/chain/`、`collector/spiders/`、`registry.py`、`03-seed.sql` | 中：全链分析 token 成本，需控频（周级） |
| D2 AI 提醒面板 | `chain_alert` 表（industry/类型/重要程度/触发条件说明/影响环节/建议关注标的）+ 分析任务产出具名告警（5 触发类型：财报异动/评级调整/技术突破/格局变化/政策催化）+ 查询 API + 产业链图谱页顶部提醒面板（按重要程度排序） | `models/`、`docker/database/migrations/`、`api/v1/chain.py`、`web/src/pages/Chain/` | 中：告警去重口径（同链同类型同日唯一） |
| D3 存储治理三件套 | ① 4 张 hypertable 开 TimescaleDB 压缩策略（`quote_kline_stock_minute` 收益最大，其余为 kline 日线/资金流/全球指数）② collector_log 90 天保留策略 ③ LangGraph checkpoint 随 assistant_session 删除级联清理（存量约 20 孤儿 thread） | `docker/database/migrations/`（均幂等） | 低：压缩段只读不影响写入路径 |
| D4 工作台板块资金卡接线 | workbench 聚合 +1 模块 sector_flow（`capital_fund_flow_sector` 数据已有，eastmoney_sector_fund_flow 任务在跑），`/workbench`「板块资金动向」空态卡换实数据（涨幅前 N + 色彩走 scheme-aware helpers） | `services/workbench/`、`api/v1/workbench.py`、`shared/types/workbench.ts`、`web/src/pages/Workbench/` | 低 |

> **实施回填（2026-09-03，批次 D 交付，分支 `feat/batch-d-chain-alerts`）**
>
> - **交付**：D1 `chain-refresh` 定时刷新四件套——复用单轮执行器 `analyze_industry_chain`（移除 DeprecationWarning 转正为定时路径载体），链级 Redis 非阻塞锁防与手动分析竞争版本号；**按用户复制落版本**：AI 每链只生成一次，对拥有该链 success 版本的每个 user_id 各落一版（created_by=scheduled），读路径零改动。D2 `chain_alert` 全局告警表（无 user_id，UNIQUE(industry, alert_type, signal_date) 吸收按用户复制与同日手动+定时双产）+ AI 结构化输出直接产告警（`ChainAnalysisResult.alerts`，5 类型 + severity 1-3，`_validate` 清洗截断 ≤10，宁缺毋滥）+ `GET /api/v1/chain/alerts`（camelCase wire，severity 降序）+ 图谱页 ChainAlertPanel（类型 Tag 配色/severity 徽标/影响环节/相关标的）。D3 存储治理迁移（幂等）：三表压缩策略（minute 14d / kline_daily 90d / fund_flow_stock 90d；quote_global_index_daily 因 us_tycr 全历史 upsert 写旧 chunk 排除）+ collector_log 90 天保留（存量 DELETE + `collector-log-cleanup` 每日 03:40）+ checkpoint 孤儿 thread 清理（to_regclass 防护）。D4 workbench +1 模块 sector_flow（最新交易日行业板块主力净流入 top8，亿元），SectorFlowCard 空态卡换实数据（涨跌色走 scheme-aware helpers + useColorScheme 订阅）。
> - **与原计划的偏差**：① 压缩策略幂等检查原查 `timescaledb_information.compression_policies`，实测 TimescaleDB 2.28 无该视图，改查 `timescaledb_information.jobs`（proc_name='policy_compression'）；② D1 原计划的"input_hash 缓存防重"未做——刷新语义即每周期产新版本（版本切换器可见），防重由告警唯一约束 + 链级锁承担；③ 渠道登记实际只落 seed/迁移的 DB 三处（任务名为键）——DEFAULT_CHANNELS 本无 internal 条目且 internal 任务豁免渠道覆盖检查，`channels.py` 无需改动；④ `ChainAlertItem.severity` 不加 ge/le 约束（单个 LLM 坏值不炸整个结构化解析），`_validate` clamp + DB CHECK 兜底。
> - **验收（API 级已过，浏览器侧待人工）**：backend unit 790 全绿/mypy/ruff；web typecheck/lint/test:unit(89)/build 全绿；docker 全量重建后 CLI 实测 `chain-refresh` SUCCESS（4 目标 3 生成：半导体×2 用户含遗留 user_id=0、锂电池、机器人；创新药因公司映射无数据单链失败被 rollback 隔离，signal_date=最新交易日）；告警唯一约束实测重复插入吸收（INSERT 0 0）；`/chain/alerts` 401/200 + camelCase + severity 降序；`collector-log-cleanup` SUCCESS 且 90 天前存量 0；三条压缩策略在册（jobs 视图）；`/workbench` sector_flow 8 行实数据；`/chain/{industry}/latest`、versions（scheduled v3 置顶）、industries 回归正常。本周模型对四链均未产出证据充分的告警（alerts=[]，宁缺毋滥生效），告警写入路径以探针行实测后清理。

### 批次 F：V1.3 导航重组与个股侧栏整合（2026-09-07 立项，纯前端快赢）

> 需求基准 [01-requirement.md §4.4.0 导航 IA 表](../requirement/01-requirement.md)。零后端依赖（板块监测数据升级除外，
> 该项在批次 G）。批次字母 E 已用于 2026-09-02~04 AI 交互范式迭代（见 §1.1），本批从 F 起编。
> 分支建议 `feat/batch-f-nav-reorg`。

| 项 | 内容 | 关键落点 | 风险 |
|----|------|----------|------|
| F1 侧边栏与移动 TabBar 重组 | 按 4.4.0 四分组 12 项：监测（宏观指数/板块监测/个股监测/集合竞价）→ 资讯（资讯中心）→ 投资日历 → 分析（每日复盘/产业图谱/板块异动/个股异动）；未实现页先以路由占位或隐藏（宏观监测/异动两页随 G/I 上线再挂出） | `web/src/components/layout/`、`router.tsx` | 低 |
| F2 研报/财报并入个股右栏 tab | 个股详情右栏四 tab：AI 分析（已有）/ 财报 / 研报 / 板块（已有）；财报·研报 tab 内 = 列表 + PDF 查看/下载 + AI 解读按钮（侧边栏助手触发 `financial-report-summary` / `research-report-summary` skill）+ 手动触发采集按钮 | `web/src/pages/StockDetail/`、`pageEvents.ts` | 中：**决策点**——手动触发采集走管理员 collector API 还是新增受限端点（普通用户白名单任务） |
| F3 旧路由处置 | `/research`、`/financial-reports`、`/hotspot` 导航与路由下线（热点能力随批次 H 并入资讯中心）；`/financial/:code` 保留为个股财务深链；外链重定向兜底 | `router.tsx` | 低 |

### 批次 G：监测分组数据扩展与双页（F-VIS-09 + F-VIS-04 扩展）

> 依赖：F1 导航就位。**数据源调研先行**（G1），调研结论回填本节后再排 G3/G4 页面实现。

| 项 | 内容 | 关键落点 | 风险 |
|----|------|----------|------|
| G1 二批全球指标调研 | 港股/美股指数：东财 push2delay `ulist.np/get` 扩展 secid（批次 A 先例，低风险）+ akshare 历史回补；日债 10Y：源待查（push2delay secid / akshare）；**加息概率：CME FedWatch 逆向（高风险）**，降级预案 = FOMC 日历会议占位 + 会前提示，不做伪数据 | 探针脚本（/tmp，用后即删） | 高（加息概率线）/ 低（指数线） |
| G2 板块行情采集 | 行业/概念板块指数快照（涨跌幅/成交额/领涨股），行业走东财 push2delay、概念源待调研（原型定稿：行业东财 / 概念同花顺）；节奏控制防 WAF（delay 镜像 + 低频）；落表 + 热力总览聚合 API | `collector/spiders/`、`models/`、`api/v1/market/` | 中：push2 系 WAF（按主机封禁先例）；概念板块源未验证 |
| G3 /macro-monitor 页 | 四类分组（股指/债券/商品/政策概率）+ 指标卡 + sparkline（`quote_global_index_daily` 日线序列）+ 港股/美股「指数级 only」标注 | `web/src/pages/MacroMonitor/` | 低 |
| G4 /capital-flow 升级 | 板块指数表现热力总览（色深=涨跌幅）+ 板块资金流向趋势 + 当日净流入/净流出排名 + 行业/概念切换（对齐 `capital-flow.html` 原型） | `web/src/pages/CapitalFlow/` | 低（数据就绪后） |

### 批次 H：资讯中心（F-VIS-10 + F-AI-03）

> 依赖：F1 导航。与批次 I 相互独立；建议先行（I 的「关联资讯时间线」可复用查询能力）。
> 全部新 AI 能力走双路径范式：SKILL.md + 侧边栏触发 + page_event 回写 / 定时 internal 任务。

| 项 | 内容 | 关键落点 | 风险 |
|----|------|----------|------|
| H1 渠道监控 API | `collector_log` 聚合各渠道最近状态/延迟/采集节奏（财联社 10s 轮询心跳、批量任务最近成功时间）→ 渠道监控条 | `api/v1/news/`、`services/` | 低 |
| H2 电报 AI 重要度分级 | **决策点**：`importance` 现为 cls 源 level（1-3），AI 分数另存（`ai_score` 0-100 + `ai_reason` 评分构成），不覆盖源数据；执行形态 = stream 增量后轻队列批量打分 | `models/news_telegraph.py`、`services/news/`、spider 后处理 | 中：打分任务节奏与 token 成本 |
| H3 重点与跟踪 | `ai_score ≥ 70` 入重点；同主题报道 ≥5 篇自动聚类故事线（新表 storyline + 条目关联 news/telegraph id）；电报流「加入跟踪」手动续接；来源标注（AI 自动建线 / 手动 / 订阅命中） | `models/`、`services/news/`、迁移 SQL | 中：聚类口径（主题相似度阈值） |
| H4 我的订阅 | 用户关键词规则表（渠道/关键词/股票代码维度）+ 命中标记回流电报流 ★（查询期实时匹配优先，避免采集耦合） | `models/`、`api/v1/users/` | 低 |
| H5 热点主题（F-AI-03） | 每日盘后 AI 任务产主题榜：主题/情绪（利好利空分歧票数分布）/ 热度构成透明化（资讯量 × 板块涨幅 × 主力净流入）/ 关联板块 / 传导链（事件→环节→代表标的）；落 `hotspot_topic` 表 | `skills/`、`services/`、TaskSpec + seed cron | 中：热度构成数据拼接口径 |
| H6 /news 页 | 三视图（实时电报[现有 /telegraph 并入]/重点与跟踪/热点主题）+ 页头我的订阅抽屉；对齐 `news.html` 原型 | `web/src/pages/News/`、`router.tsx` | 低（数据就绪后） |

### 批次 I：板块与个股异动分析（F-AI-09 / F-AI-10）

> 依赖：F1 导航；建议 H 之后（关联资讯时间线复用）。检测（规则算子）与归因（AI）分离：
> 检测为确定性统计任务（盘后跑），归因按需/每日 top-N 触发控 token。

| 项 | 内容 | 关键落点 | 风险 |
|----|------|----------|------|
| I1 板块异动检测 | 规则算子：涨跌幅偏离基准（±2%）/ 量能放大（5/20 日均值的倍数）/ 资金突变（主力净流入连续性）/ 齐动性（板块内个股同涨占比）；盘后任务落 `sector_anomaly`（含异动强度分） | `services/market/`、`models/`、TaskSpec + seed cron | 低（数据已有：板块行情随 G2、资金流在跑） |
| I2 板块 AI 归因 | 归因类型（事件驱动/资金驱动/轮动补涨）+ 关联资讯时间线 + 命中产业链直达链接（F-AI-01 图谱行业映射）；每日 top-N 归因 + 页面手动重新分析（侧边栏 + page_event） | `skills/`、`services/` | 中：token 成本（top-N 控量） |
| I3 个股异动检测 | 量比/换手/振幅阈值 + 大单净占比 + 龙虎榜命中 + 公告/电报联动（当日关联标记）+ 分时急拉/尾盘异动（分钟线）；自选交集命中标记 | `services/market/`、`models/` | 中：分钟线扫描量（限定自选+涨幅初筛集） |
| I4 个股 AI 归因 | 独立异动 vs 板块带动（对照 I1 当日板块异动清单）+ 归因摘要 + 跳个股监测/资讯时间线 | `skills/`、`services/` | 中：同 I2 |
| I5 异动双页 | `/anomaly/sector` + `/anomaly/stock`：异动强度排序清单（标签 + 归因摘要）+ 回看图 + 关联资讯 + 产业链直达 + 自选 ★ 高亮；对齐 `sector-anomaly.html` / `stock-anomaly.html` 原型 | `web/src/pages/Anomaly/`、`pageEvents.ts` | 低（数据就绪后） |

### 批次 J：技能广场前端（F-USER-04，2026-09-07 立项）

> 后端契约由重构批次 7 交付（PR #26）：`GET /api/v1/skills`（available + mine 分组）、
> install/uninstall、custom CRUD + 发布；`shared/types/skill.ts` camelCase 类型已就绪，web 页面/hooks 全缺。
> 原型基准 `docs/prototypes/skill-square.html`（2026-09-07 定稿）。
> 分支建议 `feat/batch-j-skill-square`。

| 项 | 内容 | 关键落点 | 风险 |
|----|------|----------|------|
| J1 广场页 | `/skills` 双 tab：广场（available = 内置 + 他人已发布 custom，kind 筛选 chips + 详情抽屉：frontmatter/提示词契约/结构化输出）+ 我的（mine：已安装行 enabled 开关 + 卸载；我的自定义卡草稿/已发布状态与操作）；内置技能「内置」徽标 + 始终可用说明（安装语义仅对 custom 有意义） | `web/src/pages/Skills/`、`shared/api/endpoints.ts`（skills 组已有）、TanStack Query hooks | 低（API 就绪） |
| J2 自定义技能管理 | 创建抽屉表单（skillId/名称/描述/SKILL.md/System Prompt/User Prompt 模板 `{placeholder}`）+ 草稿编辑（version+1）+ 发布 + 删除；skillId 撞内置保留字或他人 custom 的 409 错误提示 | 同上 + AntD Form/Drawer | 低 |
| J3 设置导航接线 | 侧边栏设置分组挂「技能广场」入口（F1 重组后为四分组内设置区）；与批次 F 的导航重组合并落地时注意顺序 | `web/src/components/layout/` | 低 |

### 后置池（不排序，触发条件成熟再评估）

- F-AI-01 增强：重大事件触发产业链刷新（告警驱动再分析）
- API-KEY 管理 + MCP Server 实装（F-API-01；终态原型基准 `settings.html`「API-KEY 与 MCP」区，2026-09-07 定稿）
- 用户级模型配置（F-USER-03；终态原型基准 `settings.html`「AI 与模型」区，2026-09-07 定稿）
- 研报 PDF 全文在线阅读、资金流向桑基图（V1.1 遗留）
- 资金流向显示方式补全（F-VIS-04 剩余项，2026-09-04 review 补录）：资金轮动热力日历、板块下钻个股资金异动、进出排行榜连续流入/流出天数趋势指示、动态迁徙图——依赖后端新增聚合/派生接口，触发条件成熟再排期
- 小程序端（Taro）
- PG 备份入 COS（硬性排最后）

## 4. 状态维护

- 每项落地后在本文件标注：`未实现` → `实现中（分支）` → `已完成（日期 + PR）`
- 批次内验收基线：backend `uv run pytest -m unit` + `mypy` + `ruff`；web `typecheck`/`lint`/`test:unit`/`build`；定时类任务按 collector 验收惯例（任务目录 API 可见、collector_log 终态、前端展示）
- 数据源调研项（A1 cls WAF 节奏、A2 渠道权限、A3 cls 签名）结论直接回填本文件对应行
