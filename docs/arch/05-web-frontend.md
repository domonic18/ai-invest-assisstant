# 前端架构设计（响应式 Web 单端版）

## 1. 多端架构总览

前端为**响应式 Web**单端实现，桌面与移动端共用一套代码，通过响应式断点与底部 Tab Bar 切换布局：

```
                      用户
                       │
        ┌──────────────┴──────────────┐
        │                              │
   ┌────┴──────────┐           ┌──────┴──────┐
   │ 桌面浏览器      │           │ 移动浏览器    │
   │ (≥1024px)      │           │ (≤768px)    │
   │ 侧边栏 + 顶部栏 │           │ 底部 Tab Bar │
   └────┬──────────┘           └──────┬──────┘
        │                              │
        └────────── HTTPS ─────────────┘
                     │
                     ▼
┌────────────────────────────────────────────┐
│ SCF Web 函数 — web 一体镜像（:9000）   │
│ React SPA（FastAPI 静态托管）· /assets/ 长缓存 │
│ FastAPI /api/* 同源 · SSE 流式输出（LLM）  │
│ invest.17aitech.com · /docs /health        │
└────────────────────────────────────────────┘
```

- **桌面端** — 全功能投资分析平台（产业链图谱 / K 线 / 资金流向 / 研报 / 财报 / 后台管理）
- **移动端** — 复盘 / 分析 / 设置三大分组 + 底部 Tab Bar + 抽屉导航，AI 助手底部弹层，图谱双指缩放

## 2. 技术栈

| 类别 | 技术 | 用途 |
|------|------|------|
| 框架 | React 18.3 + TypeScript 5.4 | 主框架 |
| 构建 | Vite 5.2 | 开发 / 构建（输出至 `dist/`） |
| 状态管理 | Zustand | auth / settings（配色+用户设置）/ drawing / screening / sidebar / assistant |
| 路由 | React Router 6.23 | 页面路由 |
| UI 组件 | Ant Design 5 + Tailwind CSS | 组件库 + 自定义布局微调 |
| K 线图 | ECharts + echarts-for-react | 行情可视化（含键盘缩放 / 平移） |
| 产业链图 | AntV/G6 v5 | 图谱可视化（自定义节点 / 分栏背景） |
| 资金流向 | ECharts | 板块河流图 + 排名图（含概念板块） |
| HTTP | axios + TanStack Query | 数据请求 / 缓存 |
| 测试 | Vitest + @testing-library/react + Playwright | 单元 / E2E |

## 3. 页面路由

```
/login                          # 登录页（OAuth2 表单，管理员经 `python -m app.cli.bootstrap_admin` 显式提权）
/register                       # 注册页

/workbench                      # 工作台（登录后默认入口）
/watchlist                      # 我的自选（分组 + AI 复盘开关 + 个股行情卡）
/review                         # 每日复盘（Dashboard）
/chain/:industry?               # 产业链分析（带行业参数，支持版本切换）
/stock/:code                    # 个股详情（同花顺式行情条 + 多周期 K 线 + 右栏 AI/财报/研报/板块 tab）
/capital-flow                   # 资金流向（板块河流图 + 排名图）
/macro-monitor                  # 宏观指数监测（股指/债券/商品/政策概率四分组）
/index/:code                    # 指数详情（A 股 K 线 + 全球指标历史线）
/auction-review                 # 集合竞价（指数成交额趋势）
/news                           # 资讯中心（实时电报 / 重点与跟踪 / 热点主题 / 订阅规则）
/calendar                       # 投资日历（月历 / 周历 / 列表三视图，分类筛选）
/anomaly/sector | /anomaly/stock # 异动检测（单页双 Tab，Tab 切换走路由、URL 可直达；侧边栏单入口 /anomaly）
/screening                      # AI 选股（问财自然语言选股）
/sector/:sectorType/:sectorCode # 板块详情（板块指数 K 线 + 成分 + 资金流）
/financial/:code                # 财务体检详情（独立入口，也嵌入个股 Tab）
/kb                             # 知识检索消费页（admin ∪ 白名单；侧边栏「知识检索」入口暂撤，见 09 号文档）
/settings                       # 个人设置（基本信息 / 外观与配色 / 指数 / AI 配额 / 我的模型 / 安全）
/skills                         # 技能广场（业务场景 Tab + 搜索 + 能力/来源徽标）
/skills/:skillId                # 技能详情（全页面：元信息 + 文件浏览 + 内容预览）

# 旧路由兜底重定向
/auction → /auction-review；/hotspot、/research、/financial-reports → /workbench（研报/财报并入个股详情右栏）；/telegraph → /news

/admin                          # 后台管理总览（ADMIN_LINKS 11 入口卡片）
├── /admin/users                # 用户管理（审批 / 配额调整）
├── /admin/stocks               # 股票管理（含列表同步任务入口）
├── /admin/reports              # 报告管理（存储统计卡片 + 清理 3 个月前报告 + 研报/财报双 Tab）
├── /admin/news                 # 资讯管理
├── /admin/llm-configs          # LLM 配置
├── /admin/mcp-servers          # MCP 服务（CRUD + 连接测试 + 工具注入开关）
├── /admin/ai-results           # 分析结果（skill Tabs + 日期/状态筛选 + 重新生成/删除）
├── /admin/collector            # 采集管理三合一 Tabs（执行与日志 / 任务配置 / 渠道配置）
├── /admin/usage-dashboard      # 用量看板（用户 token 分项 + KB 建库用量）
├── /admin/knowledge-base       # 知识库管理台（六页签，见 09 号文档）
├── /admin/social-tracking      # 社媒大 V 追踪管理（见 08 号文档）
├── /admin/system-status        # 服务状态（F-MON 采集健康）
├── /admin/proxy-configs        # 代理配置（仅侧边栏子菜单进入，不占主页卡片）
├── /admin/tasks → /admin/collector?tab=tasks            # 旧路由重定向
└── /admin/collector-channels → /admin/collector?tab=channels  # 旧路由重定向
```

> 侧边栏分组：工作台 / 我的自选 / 检测（宏观指数 · 资金流向 · 集合竞价 · 异动检测）/ 资讯（资讯中心 · 投资日历）/ 分析（每日复盘 · 产业图谱）/ 设置（个人设置 · 技能广场 · 后台管理子菜单），移动端折叠为底部 Tab Bar。
>
> AI 助手全局入口：Header 右侧「AI 助手」按钮 + 任意页面右下角猫头鹰悬浮按钮（AssistantFab），唤起 assistant-ui 侧边面板。

## 4. 核心页面

### 4.1 工作台（登录默认入口）

卡片化聚合页（`/workbench`，登录后默认路由；每日复盘保留为独立页，复盘状态摘要在左侧导航栏常驻）：

| 模块 | 内容 |
|------|------|
| 指数条 | A 股核心指数 + 全球指标实时卡片（黄金 / 美元指数 / 美债收益率），点击进指数详情 |
| 美联储加息概率 | FOMC 加息 / 降息概率卡 |
| 财联社电报 | 10s 准实时电报流（AI 重要度分级标记） |
| 投资日历摘要 | 近 7 日关键事件，点击进入完整日历 |
| 自选股概览 | 分组行情卡 + 当日 AI 每日分析摘要（六分区） |
| 采集引擎状态 | 采集任务运行 / 队列状态概览，跳转后台采集管理 |
| 板块资金流 | 当日板块净流入 / 流出榜 |

模块卡片可折叠；各模块数据缺失时展示空态而非报错。

### 4.2 每日复盘（Dashboard）

桌面 / 移动端均展示：指数 K 线（多标的）+ 行情统计 + 板块表现 + 涨停复盘 + AI 大盘综述 + 自选股行情卡。
- 顶部提供补采入口（盘后三态空态：未开盘 / 盘中 / 已收盘）
- AI 综述支持模块级编辑（每个分区独立保存）
- 涨停复盘按行业分组（同花顺风格），含 AI 归因、行对齐与分时缩略图

### 4.3 产业链全景分析（核心页面）

G6 v5 关系图谱 + 行业选择器 + 版本切换（版本化分析经 AI 助手确认生成）；自定义节点与上中下游分栏背景，基于经营范围自下而上推导环节；移动端双指缩放，下方面板展示版本对比 / 节点详情与关键指标。

### 4.4 个股详情（同花顺风格）

行情条（标识 / 现价 / 快照 10 项 / 加入自选）+ 双图单元（各自独立周期与指标，可切单图；拖拽分栏调高度）+ 右栏 Tabs：

- **K 线图**：键盘缩放 / 平移；⚙ 图表设置弹层（涨跌配色即时切换、复位缩放窗口、「更多设置」跳个人设置）
- **AI 分析 Tab**：六分区每日分析（盘中回顾/技术面/情绪面/关键事件/策略/风险线，盘后 16:40 定时生成），固定附"AI 生成，不构成投资建议"免责声明
- **财务 Tab**：当期财务体检评分 + 近 8 期历史趋势 + 财报列表（PDF / AI 摘要 / 手动触发采集）
- **研报 Tab**：研报列表（PDF + AI 解读 + 采集触发）
- **板块归属 Tab**：行业 + 概念板块

### 4.5 资金流向 / 集合竞价 / 投资日历

- **资金流向**：行业板块走东财 / 概念板块钉死同花顺（东财 WAF 按 TLS 指纹 + 主机限流）；河流图按时间轴展示净流入流出演化，排名图展示当日 TOP 行业 / 概念；金额按流入红 / 流出绿着色（订阅 `useColorScheme`）
- **集合竞价**：指数集合竞价成交额趋势图（口径走 Tushare `stk_auction` 聚合；不使用新浪分钟线——首根 bar 盘后被修订）
- **投资日历**：月历 / 周历 / 列表三视图，今日高亮 + 分类筛选（宏观数据 / 央行动态 / 新股 / 解禁 / 财报 / 会议 / 自选相关）；数据来自 `news_calendar_event`（财联社日历 + FOMC / BLS 固定日程）

### 4.6 研报 / 财报（并入个股详情）

研报与财报不再有独立中心页，统一并入个股详情右栏 tab（旧路由重定向回工作台）：列表 + 预签名 URL 下载 PDF + AI 摘要（缓存 `file_metadata.summary`）+ 手动触发采集（返回 log_id 可查采集日志）。报告管理在后台统一维护。

### 4.7 技能广场（/skills）

- **技能市场**：业务场景 Tab（枚举来自 `shared/types/skill.ts`）+ 搜索；能力徽标（自动化·定时 / 对话调用 / 方法论 / 自定义）与来源徽标（官方 / 自定义），整卡进入全页详情 `/skills/:skillId`，安装 / 卸载就地操作
- **我的技能**：启用 / 停用 / 卸载；自定义技能（配置非代码）创建 / 编辑 / 发布
- **上传解析**：创建表单支持上传标准 zip（须含 SKILL.md），`POST /skills/analyze` 解析 frontmatter 自动预填（zip-slip / secret 防护）

### 4.8 个人设置

- **基本信息**：用户名 / 邮箱
- **外观与配色**：涨跌配色方案开关（红涨绿跌 / 绿涨红跌），全站自动应用；个股详情 ⚙ 弹层亦可即时切换
- **指数 / AI 配额 / 我的模型**：跟踪指数展示偏好；个人配额与用量视图；BYOK 自备模型 Key（见 07 号文档）
- **K 线均线**：用户级 MA 周期列表（存 `user.settings` JSONB，默认值真相源 `stores/settings.ts`），**新注册账户默认 MA5 / 10 / 20 / 30 / 60**（MA120 关）
- **账号安全**：修改密码

### 4.9 后台管理（11 入口 + 代理配置）

| 页面 | 功能 |
|------|------|
| 总览 | ADMIN_LINKS 11 入口卡片 + 最近采集日志 |
| 用户管理 | 列表 / 角色 / 启用 / 注册审批与配额调整 |
| 股票管理 | 列表 / 字段补全 / 同步任务入口 |
| 报告管理 | 存储统计 + 「清理 3 个月前报告」（二次确认）+ 研报 / 财报双 Tab |
| 资讯管理 | 列表 / 删除 |
| LLM 配置 | provider / base_url / api_key 加密存储 |
| MCP 服务 | 三通道动态表单 + JSON 导入预填 + 连接测试 + 启用注入开关（启用即注入 AI 助手） |
| 分析结果 | skill Tabs + 日期 / 状态筛选；「AI 重新生成」经侧边栏助手触发；删除为缓存清除语义 |
| 采集管理 | 三合一 Tabs：执行与日志 / 任务配置（`collector_task` CRUD）/ 渠道配置（优先级降级链） |
| 用量看板 | 用户 token 用量分项（模型 / feature 维度）+ KB 建库用量面板 |
| 知识库管理台 | 六页签（列表 / 素材接入 / 知识审核 / 图片资产 / 知识检索 / 设置），见 09 号文档 |
| 社媒追踪 | 大 V 账号管理 + 作品与情绪排查抽屉，见 08 号文档 |
| 服务状态 | 采集健康监测（任务级状态 / 连败告警），见 02 号文档 |
| 代理配置 | 采集出口代理 CRUD，仅侧边栏子菜单进入 |

### 4.10 异动检测 / AI 选股 / 知识检索

- **异动检测（`/anomaly`）**：单页双 Tab（板块 / 个股），Tab 切换走路由（`/anomaly/sector` | `/anomaly/stock`）；交易日切换 + 异动榜（强度排序 / 维度筛选 / 分类徽标 / 趋势事实摘要）+ 行内 AI 归因（侧边栏触发）。检测与归因机制见 [06](./06-anomaly-analysis.md)。
- **AI 选股（`/screening`）**：问财自然语言选股（助手 `screen_stocks` 工具同源能力）。
- **知识检索（`/kb`）**：admin ∪ 白名单门控的消费页（搜索三类命中 + 播放器 / 阅读器直达）；管理台入口 `/admin/knowledge-base`。链路见 [09](./09-knowledge-base.md)；侧边栏「知识检索」入口暂撤，启用时点待定。

## 5. 组件化封装

### 5.1 封装层次与目录

```
web/src/
├── components/
│   ├── layout/             # 框架壳：Header / Sidebar / Layout / MobileTabBar
│   ├── charts/             # 行情与图谱可视化组件族（见 5.2）
│   │   ├── stockChartView/ # 个股双图单元拆分（klineOption / klineData / klinePanes …）
│   │   └── drawing/        # K 线画线图层组件族（见 5.3）
│   ├── assistant/          # AI 助手面板组件族（见 5.4）
│   ├── common/             # 跨页面纯展示：Brand / MarkdownText / SourceNote
│   └── auth/               # 路由守卫：ProtectedLayout / ProtectedAdmin / RedirectIfAuthenticated
├── hooks/                  # TanStack Query 包装（服务端数据获取唯一入口）
├── stores/                 # Zustand（auth / settings / drawing / screening / sidebar / assistant）
└── pages/                  # 页面级组件，私有组件留在页面目录内
```

### 5.2 图表组件族（components/charts/）

| 组件 | 载体 | 用途 | 要点 |
|------|------|------|------|
| `KlineChart` | ECharts | 个股多周期 K 线 | 键盘缩放/平移（`useKlineKeyboardNav`）、均线订阅用户设置、异动 markers、画线图层挂载 |
| `IndexKlineChart` | ECharts | 指数 K 线（复盘/指数详情） | 同上，画线图层挂载 |
| `IntradayChart` / `IntradaySpark` | ECharts | 分时图 / 迷你走势 | 竞价趋势、行情卡 sparkline |
| `ChainGraph` | AntV/G6 v5 | 产业链关系图谱 | 自定义节点、上中下游分栏背景、双指缩放、版本切换 |
| `FinancialTrendCharts` | ECharts | 财务近 8 期趋势 | 毛利率/净利率/ROE 等 |
| `StockChartView` | 组合 | 个股双图单元 | option 构造与数据适配拆分于 `stockChartView/`（klineOption / klineData / klinePanes…） |

### 5.3 K 线画线图层组件族（components/charts/drawing/）

**设计原则**：

1. **锚点即契约**：画线一律存数据坐标 `(date, price)`，像素只在渲染瞬间存在——K 线追加 / 缩放 / 跨周期下语义稳定，LLM 与前端读写同一套坐标语义
2. **图层与主图解耦**：经 `<DrawingLayerHost>` 以组合方式接入个股（StockChartView）与指数（IndexKlineChart）两套图表，图层异常降级为「不渲染」，不侵入主图交互（十字光标 / 键盘导航 / 异动 markers）
3. **用户画线与 AI 画线物理分表**，均 per-user 私有：用户画线是长期资产；AI 画线是会话属主的可变工作区（采纳 / 编辑 / 清空）
4. **读写共用一份 wire 契约**（`shared/types/drawing.ts`，后端 Pydantic CamelModel 镜像同构）；写路径人工优先——AI 画线前必须经问题卡确认

渲染选型结论：ECharts `graphic` + zrender 事件（原生命中检测与拖拽），`convertToPixel/convertFromPixel` 承担数据↔像素换算；markLine 仅保留既有异动日 markers。

**组件清单**：

| 分组 | 文件 | 职责 |
|------|------|------|
| 纯函数层 | `types.ts`（re-export shared/types）/ `coordinates.ts` / `geometry.ts` / `chartInternals.ts` / `shapeSpecs.ts` | 数据↔像素换算、射线延伸、5 类型→graphic 规格（单测钉死） |
| 交互状态 | `draftMachine.ts` / `layerEvents.ts` / `sessions.ts` | idle→armed→drafting→selected→dragging 状态机；dataZoom/resize/finished 视图联动；草稿会话 |
| 宿主与挂载 | `useDrawingLayer.ts` / `DrawingLayerHost.tsx` | 渲染 / 重定位 / 命中托管；**对外唯一接入入口** |
| UI | `DrawingToolbar.tsx` / `DrawingSideBar.tsx` / `StyleBar.tsx` / `DrawingTextInput.tsx` / `AiDrawingButton.tsx` / `DrawingsPanel.tsx` | 工具条、样式条（6 色/线型/线宽）、文字输入、AI 入口、画线清单（用户组 + AI 组） |

**数据流与 AI 双向接线**：

- 服务端状态走 TanStack Query `['kline-drawings', targetType, targetCode]`，一次拉取该标的**全周期**画线（user + ai 两组，周期切换纯前端过滤，零请求）；客户端状态走 zustand `drawingStore`，变更即 mutation 乐观更新 + 失败回滚 toast
- x 轴为 category（bar 日期）：锚点对齐「≤ 该日期的最后一根 bar」，越界裁剪于绘图区边缘；视图联动对每条画线重算像素后按同 id 增量 `setOption`（禁止整图重设，保拖拽帧率）
- **读**（画线 → 上下文）：`get_kline_drawings(target_type, target_code)` 助手工具按会话属主返回结构化 JSON；共享复盘缓存（全局一份）**不注入**用户私有画线——多租户隔离
- **写**（对话 → AI 画线）：`kline-smart-drawing` skill 取数分析 → 已有画线时 `ask_user` 问题卡（replace / append / 删除重画 / 取消）→ `persist_ai_kline_drawings(mode, drawings[])` → `page_event("kline_drawing.complete")` 经 SSE 回写，前端订阅刷新 AI 图层
- **ask_user 问题卡（通用交互底座）**：`ask_user(question, options, default?)` 以结构化问题结束本轮，runtime 检测标记后经 SSE 下发 `question` 事件，`QuestionCard` 渲染选项按钮，点击即作为新消息续跑线程；任何需要用户决策的交互式 skill 可复用，定时任务路径不使用

**后端对接一览**（架构级）：服务 `services/market/kline_drawing_service.py`（用户 CRUD + AI 集读写，强校验 user_id 归属）；`api/v1/drawings.py` 8 端点（GET/POST/PATCH/DELETE `/kline-drawings` + `ai/adopt` + `ai/item` PATCH/DELETE + `ai/clear`）；表 `user_kline_drawing` / `ai_kline_drawing` 见 03 号文档 §3.8。分钟线不提供画线；移动端只读展示。

### 5.4 AI 助手面板组件族（components/assistant/）

| 组件 | 职责 |
|------|------|
| `RuntimeProvider` 等 | assistant-ui 运行时接线：runs 流 / SSE / 中断 / 配额错误帧引导 |
| `Thread` / `Composer` / 会话侧栏 | 对话流渲染、输入区、历史会话管理（`assistant_session` 持久化） |
| `QuestionCard` | ask_user 问题卡选项渲染（见 5.3） |
| `pageEvents.ts` | `PAGE_EVENT_DEFINITIONS` 唯一映射点：page_event → camelCase 字段 + 查看按钮 + 结果页路由 |

页面接入范式：按钮调 `useAssistantStore.getState().sendQuestion(prompt)` 打开侧边栏并预置问题；结果回写用 `usePageAssistantResult('<domain>.complete', cb)` 订阅（invalidateQueries + toast）。

### 5.5 组件维护规范

1. **目录归属**：可视化 → `charts/`；跨页面纯展示 → `common/`；页面私有组件留在页面目录内；数据获取一律经 `hooks/` 的 TanStack Query 包装，服务端状态不进 zustand
2. **单文件 ≤350 行**：图表 option 构造、数据适配拆到同目录子模块（范本 `stockChartView/`）
3. **契约单一真相源**：wire 类型一律 `shared/types`，组件内不得重复声明；后端 CamelModel 镜像同构，改契约先枚举两端消费者
4. **配色语义**：涨跌色只经 `useColorScheme()` + formatters 的 scheme-aware helpers 输出，组件不得硬编码红绿
5. **新图表接入画线**：以 `<DrawingLayerHost>` 组合挂载，不复制图层逻辑
6. **测试与被测同目录**（`*.test.ts(x)`），纯函数（geometry / draftMachine）优先单测钉死

## 6. 共享代码层（`shared/`）

```
shared/                       # 独立 npm 包，被 web 与 backend（uv）共享
├── api/
│   ├── endpoints.ts          # API 端点常量
│   └── index.ts
├── types/
│   ├── stock.ts / chain.ts / market.ts / admin.ts / api.ts / user.ts
│   └── …（account / anomaly / calendar / drawing / kb / mcp / news / skill / social / telegraph / workbench 等，共 17 个域文件 + index.ts）
└── utils/
    └── ...
```

## 7. 构建与托管

- **Vite**：`manualChunks` 三组（vendor：react 系 / charts：echarts+g6+d3 / ui：antd）——图表库变动不影响业务 chunk 缓存；alias `@` → `src`；dev server `/api` 代理 `:8000`
- **SPA 托管**（FastAPI 内置，web 一体镜像单 uvicorn 进程直听 :9000，无代理层）：`/assets/` 长缓存（内容哈希 + immutable），`/index.html` 与 SPA 路由 fallback 禁缓存（发版即生效）；HSTS / CSP 仅 HTTPS 下发，`FORCE_FORWARDED_HTTPS=1`（SCF）强制 scheme=https；API 未匹配路径保持 JSON 404 不落 index.html

## 8. 后续文档索引

- [00-overview.md](./00-overview.md) — 总体架构与目录结构
- [03-data-storage.md](./03-data-storage.md) — 画线 / 配额等相关表设计
- [04-ai-agent.md](./04-ai-agent.md) — AI Agent 体系（前端如何调用版本化分析）
- [06-anomaly-analysis.md](./06-anomaly-analysis.md) — 异动检测与归因
- [07-account-quota.md](./07-account-quota.md) — 账户与 AI 配额（BYOK / 用量视图）
- [08-social-sentiment.md](./08-social-sentiment.md) — 社媒追踪管理台
- [09-knowledge-base.md](./09-knowledge-base.md) — 知识库消费页与管理台
