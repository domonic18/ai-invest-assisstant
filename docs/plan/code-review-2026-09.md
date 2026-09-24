# 代码重构计划（2026-09）

> **状态：已完成（2026-09-15，PR #50 合入 develop）**——批次 A–E 全部落地并通过验收（backend pytest/mypy/ruff、web typecheck/test/build 全绿）。
> 基线：`feature/account-quota` 工作区（2026-09-14），来源：全仓代码评审收敛。行号以该时点为准，仅供追溯。
> 只含高优必做项，合计约 10.5 人日；批次独立执行、独立验收。

## 批次 A · 迭代 10 分支合入前置（约 3 人日）

| # | 任务 | 位置与改法 |
|---|------|-----------|
| A1 | 路由层事务下沉 | `api/v1/admin/account.py:86-105` 路由内编排 upsert+审计+commit+失效镜像 → 下沉为 `approval_service.apply_settings(admin, data, ip)`，路由只留 HTTP 转译与参数钳制 |
| A2 | 看板分桶可测化 | `services/quota/usage_query_service.py:17-19,105,209` 分桶用 PG 专有 `AT TIME ZONE`（sqlite 测不了）→ 抽 `_cn_bucket_day(dt) -> date` 纯函数；补 `get_quota_view`/`list_usage` 单测 |
| A3 | 悬挂预扣回补 | `agent/runtime/usage_meter.py:94-100` `_prune_stale` pop 前对 `reserved>0` 项 `settle(user, reserved, 0)` 回补（方法改 async，调用点 `_start` 本就是 async） |
| A4 | 降级恢复窗口防超额回补 | `quota_service.py:139-152` Redis 故障期 PG 放行未预扣，恢复后 settle 会 INCRBY 虚增 → 降级路径返回独立哨兵，meter 据此置 `reserved=0` |
| A5 | precheck 根治 | 5 处 `precheck`+`meter_scope` 二连合并为单个 FastAPI dependency（新 AI 端点漏接即不可能）；补端点级测试断言余量为 0 → 429；`tests/unit/api/test_assistant.py:40-44` 等 4 处 autouse 放行桩收敛为共享 fixture |
| A6 | 迁移命名与文档修正 | `migrations/20260914_account_quota.sql:26,49-55,68,81-82` 的 chk_/idx_ 补表名前缀（同步 01-schema.sql，趁未上生产）；`docs/arch/10-account-quota.md:16` 迁移文件名 20260915→20260914 |

验收：分支门禁全绿 + 新增测试通过。

## 批次 B · 正确性止血（约 2.5 人日）

| # | 任务 | 位置与改法 |
|---|------|-----------|
| B1 | 分页校验统一 | `api/v1/kline.py:23-24`、`fund_flow.py:37-38`、`auction.py:42-43`、`admin/collector.py:132` 裸 `page/page_size`（page=0 → 负 offset → 500）→ `Query(ge=1, le=...)`，常量统一用 `app/constants/pagination.py` |
| B2 | 422 通道修复 | `api/v1/research.py:35-40`、`financial_report.py:37-40` 路由体内手工构造请求模型，越界值抛 ValidationError 成 500 → 分页参数改 `Query` 约束或 `Depends()` 注入 |
| B3 | 结构化输出去默认值 | `services/reports/financial_report_summarizer.py:21-25`、`research_service.py:31-35`（10 字段全 `=""`）、`schemas/chain.py:33,104-106`（顶层 4 列表 `default_factory=list`）→ 全部改必填；补「输出 schema 无默认字段」钉死测试（防 news-score 空结果事故复发） |
| B4 | 计时锚点并发串扰 | `agent/tools/market_tools.py:34-53` 模块级 `_review_gen_start` 全局锚点跨会话互相覆盖 → 改 `contextvars.ContextVar` 或并入 usage_meter 计时 |
| B5 | 健康监测三修 | `services/collector/health/health_service.py:316-318` 交易日历窗口按查询日动态推导 + API `date` 范围校验；`:111-115` 单实例判定失败补 `logger.exception`；`health_snapshot.py:122` `last_records_date` 用 aware UTC 取日跨日错一天 → 改 CN 日 |
| B6 | 登录失败误杀修复 | `web/src/api/client.ts:61-64` 拦截器对一切 401 清 token 整页跳 `/login`，而登录接口失败正是 401 → 对 `ENDPOINTS.auth.login` 豁免；`client.test.ts` 补 401 分支用例 |
| B7 | financial-report 日期参数失效 | `runtime/specs/fundamental.py:69` `start_date/end_date` 误声明 `config_params`（spider 只从 collect kwargs 消费，管理端传参被静默丢弃）→ 改 `run_params`（对照同文件 disclosure）；补 runner→collect kwargs 贯通测试 |
| B8 | 预扣键 TTL 修正 | `services/quota/quota_service.py:47,57` reserve/settle 均 EXPIRE 续期，活跃用户键永不过期、悬挂预扣无限期滞留 → settle 移除 EXPIRE（悬挂预扣最长 7d 后由 PG 重建吸收） |
| B9 | 画线锚点契约收敛 | `kline_drawing_service.py:35-41` 与 `drawing_tools.py:29-35` 重复定义锚点数 → `REQUIRED_ANCHORS` 移入 `app/constants/drawing.py` 两侧同源导入；顺带统一 label 上限（tool 50 / API 100 现不一致） |

验收：触达端点 422/正常双态用例；空输入不可能产出全空摘要；管理端传日期区间对 financial-report 生效。

## 批次 C · 规范固化（0.25 人日）

CLAUDE.md 增补三条铁律（各一行检查项，防同类问题第三次出现）：

1. 结构化输出 schema 字段禁带默认值——默认值不进 required，LLM 会静默省略该字段
2. 列表端点分页统一走 `app/constants/pagination.py` 常量 + `Query` 约束
3. 涨跌色必须走 formatters 的 scheme-aware helpers，禁止硬编码 text-red/green

## 批次 D · K 线画线组件族大文件拆分（约 3 人日）

> 范围：`web/src/components/charts/` 下 K 线相关大文件——`useDrawingLayer.ts`（1041 行，实混居六职责）、`klineOption.ts`（579 行）、`IndexKlineChart.tsx`（412 行）及个股/板块接入层。NewsFeedView/Settings 见批次 E；ChainGraph 不在计划内。

| # | 任务 | 内容与改法 |
|---|------|-----------|
| D1 | 拆分前置护栏（必做，先行） | 补四组测试锁定现行为：①拖拽交互——zr 事件模拟 mousedown→mousemove→mouseup，断言锚点拖拽形状跟随与落库 anchors、move 拖拽兄弟镜像与 `dragMoved` 阈值；②AI 图层渲染——徽标 `-1/-2`、命中线 `-3` 仅编辑态、非编辑态无交互属性；③armed 门控——activeTool 置位后 dataZoom `disabled` + tooltip 隐藏、退出还原、teardown 还原；④后端 `upsert_ai_group(mode="append")` 撞名原位替换（service 与 tool 两级） |
| D2 | 抽 ECharts 内部通道层 | 新建 `drawing/chartInternals.ts`：`isDrawingElement`/`getMainGridRect`/`viewFingerprint`/`dataZoomCount`/`getZrEl`/`safeSetOption`（useDrawingLayer.ts:147-256 的 60 行强转集中单点封装，注释版本依赖）——纯搬家，风险最低，先做 |
| D3 | 统一用户/AI 双模 spec 构建 | 新建 `drawing/shapeSpecs.ts`：抽 `buildShapeSpecs({baseId, drawingType, anchorsPx, grid, style, extras, interactive, hooks})` 单一实现，消除 `userShapeSpecs`(:267-339) 与 `aiSpecs`(:357-455) 对四类画线的平行复制及渲染循环 DragHooks 双份闭包(:617-704)；含 lineSpec/hitLineSpec/handleSpecs/draftSpecs/elementIds，hooks 以参数传入保持纯函数 |
| D4 | 抽坐标换算与会话生命周期 | 新建 `drawing/coordinates.ts`（`makeCoordinates(chart, dates)` → anchorToPx/pxToAnchor/drawingPx）与 `drawing/sessions.ts`（DragSession + createSessions + handleDragMove/finishDrag，会话对象显式传参，消除闭包隐式共享）——与 D3 耦合最深，最后拆 |
| D5 | 主 hook 收口 | `useDrawingLayer.ts` 缩至 ~250 行：仅剩两个 effect 装配 + render 主循环；依赖方向 `types → geometry → chartInternals → shapeSpecs/coordinates → sessions → useDrawingLayer` 严格单向 |
| D6 | 接入层去重 | `StockChartView.tsx:123-169` 与 `SectorKlineView.tsx:94-140` 的 `resetZoom`/`handleDataZoom`/`toIndex` 55 行逐字复制 → 抽 `useDataZoomYAxisRescale(chartRef, chartData)` hook |
| D7 | K 线 option 层拆分 | 抽 `charts/chartShared.ts`（`fmt`/`signed`/`WEEKDAYS`/`FONT_MONO`/markLine label 配置，消除 klineOption.ts:100-107 ≡ IndexKlineChart.tsx:17,32-38 重复）；`klineOption.ts` 按 prepareKlineData / computePaneLayout+副图 builder / 主装配拆三段 |

验收：现有 drawing 测试全绿 + D1 四组新测试全绿；无 >500 行 K 线组件文件；加一种画线类型只需改一处 spec 构建实现。

## 批次 E · 页面级大文件拆分（约 1.5 人日）

| # | 任务 | 内容与改法 |
|---|------|-----------|
| E1 | NewsFeedView 抽公共 Feed 骨架 | `pages/News/components/NewsFeedView.tsx`（505 行）：TelegraphFeed(:321-377) 与 FlashFeedView(:411-458) 的「跨日分组列表 + 分页 + 更新时间/自动刷新头」~150 行结构重复 → 抽 `FeedList`（children 渲染条目）+ `FeedToolbar`；NewsEntry/FlashEntry/StockTags 拆入 `NewsFeedEntry.tsx`，主文件降至 ~200 行 |
| E2 | Settings 按 section 拆分 | `pages/Settings/Settings.tsx`（478 行）：资料/安全/均线/外观/账户多 section 混居（SECTIONS + IntersectionObserver + 3 套表单逻辑）→ 每 section 拆入 `pages/Settings/components/`（照搬同目录 TrackedIndexSettings/MovingAverageConfigList 既有模式），主文件降至 ~200 行 |

验收：两文件及其拆出件均 ≤350 行；页面行为与现有测试不变。
