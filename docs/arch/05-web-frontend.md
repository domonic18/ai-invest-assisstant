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
│ SCF Web 函数 — web-api 一体镜像（:9000）   │
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
| 状态管理 | Zustand | auth / colorScheme / userSettings 等全局状态 |
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
/financial/:code                # 财务体检详情（独立入口，也嵌入个股 Tab）
/settings                       # 个人设置（基本信息 / 配色 / K 线均线 / AI 与模型 / API-KEY / 安全）
/skills                         # 技能广场（业务场景 Tab + 搜索 + 能力/来源徽标）
/skills/:skillId                # 技能详情（全页面：元信息 + 文件浏览 + 内容预览）

# 旧路由兜底重定向
/auction → /auction-review；/hotspot、/research、/financial-reports → /workbench（研报/财报并入个股详情右栏）；/telegraph → /news

/admin                          # 后台管理总览（ADMIN_LINKS 8 入口卡片）
├── /admin/users                # 用户管理
├── /admin/stocks               # 股票管理（含列表同步任务入口）
├── /admin/reports              # 报告管理（存储统计卡片 + 清理 3 个月前报告 + 研报/财报双 Tab）
├── /admin/news                 # 资讯管理
├── /admin/llm-configs          # LLM 配置
├── /admin/mcp-servers          # MCP 服务（CRUD + 连接测试 + 工具注入开关）
├── /admin/ai-results           # 分析结果（skill Tabs + 日期/状态筛选 + 重新生成/删除）
├── /admin/collector            # 采集管理三合一 Tabs（执行与日志 / 任务配置 / 渠道配置）
├── /admin/proxy-configs        # 代理配置（仅侧边栏子菜单进入，不占主页卡片）
├── /admin/tasks → /admin/collector?tab=tasks            # 旧路由重定向
└── /admin/collector-channels → /admin/collector?tab=channels  # 旧路由重定向
```

> 侧边栏分组：工作台 / 我的自选 / 监测（宏观指数 · 板块监测 · 集合竞价）/ 资讯（资讯中心 · 投资日历）/ 分析（每日复盘 · 产业图谱）/ 设置（个人设置 · 技能广场 · 后台管理子菜单），移动端折叠为底部 Tab Bar。
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
| 自选股概览 | 分组行情卡 + 当日 AI 每日分析摘要（三段式） |
| 采集引擎状态 | 采集任务运行 / 队列状态概览，跳转后台采集管理 |
| 板块资金流 | 当日板块净流入 / 流出榜 |

模块卡片可折叠；各模块数据缺失时展示空态而非报错。

### 4.2 每日复盘（Dashboard）

桌面 / 移动端均展示：指数 K 线（多标的）+ 行情统计 + 板块表现 + 涨停复盘 + AI 大盘综述 + 自选股行情卡。
- 顶部提供补采入口（盘后三态空态：未开盘 / 盘中 / 已收盘）
- AI 综述支持模块级编辑（每个分区独立保存）
- 涨停复盘按行业分组（同花顺风格），含 AI 归因、行对齐与分时缩略图

### 4.3 产业链全景分析（核心页面）

```
┌──────────────────────────────────────────────────────────────┐
│ [行业选择器 ▼] [版本切换 ▼]  [AI 助手确认]  [紧凑工具栏]    │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────── 产业链关系图谱 (G6 v5) ──────────────┐    │
│  │   自定义节点 + 分栏背景（上中下游） + 边样式            │    │
│  │    [硅材料] ──→ [晶圆制造] ──→ [芯片设计] ──→ [...]   │    │
│  │   基于经营范围自下而上推导环节                          │    │
│  │   移动端：双指缩放                                       │    │
│  └───────────────────────────────────────────────────────┘    │
│                                                               │
├──────────────────────────┬────────────────────────────────────┤
│  版本对比 / 详情面板      │  关键指标 / 节点详情               │
└──────────────────────────┴────────────────────────────────────┘
```

### 4.4 个股详情（同花顺风格）

```
┌──────────────────────────────────────────────────────────────┐
│  行情条：标识 / 现价 / 快照 10 项 / 加入自选                  │
├──────────────────────────────────────────────────────────────┤
│  双图单元（各自独立周期与指标，可切单图；拖拽分栏调高度）     │
│   ┌──────────── K 线图（键盘缩放 / 平移） ──────────────┐   │
│   │  工具栏：周期 · 指标(VOL/MA/MACD/KDJ) · 双图/单图     │   │
│   │  ⚙ 图表设置弹层：涨跌配色 / 复位缩放窗口 / 更多设置   │   │
│   └──────────────────────────────────────────────────────┘   │
│                                                               │
│  右栏 Tabs：AI 分析 │ 财务 │ 研报 │ 板块归属                  │
│   - 财务 Tab：                                                │
│     当期财务体检评分 + 近 8 期历史趋势图                       │
│     财报列表（查看 PDF + AI 摘要 + 手动触发采集）             │
│   - 研报 Tab：研报列表（PDF + AI 解读 + 采集触发）            │
│   - 板块归属 Tab：行业 + 概念板块（基于 mapping_stock_concept）│
│   - AI 分析 Tab：盘面解读 / 操作策略 / 止损线（盘后定时生成） │
│     固定附"AI 生成，不构成投资建议"免责声明                    │
└──────────────────────────────────────────────────────────────┘
```

> ⚙ 图表设置弹层（ChartToolbar Popover）：涨跌配色即时切换（红涨绿跌 / 绿涨红跌）、复位缩放窗口、「更多设置」跳转个人设置页（均线等图表配置的统一入口）。

### 4.5 资金流向（板块河流图 + 排名图）

- 行业板块走东财 / 概念板块钉死同花顺（东财 WAF 按 TLS 指纹 + 主机限流，概念口径走同花顺采集更稳）
- 河流图按时间轴展示板块净流入流出演化
- 排名图展示当日 TOP 行业 / 概念
- 金额按流入红 / 流出绿着色（订阅 `useColorScheme`）

### 4.6 集合竞价复盘

- 改为指数集合竞价成交额趋势图（口径走 Tushare `stk_auction` 聚合）
- 不再使用新浪分钟线（首根 bar 盘后立即被修订）

### 4.7 投资日历

- 月历 / 周历 / 事件列表三视图切换，今日高亮 + 未来事件按临近度排序
- 事件分类筛选：宏观数据 / 央行动态 / 新股 / 解禁 / 财报 / 会议 / 自选相关
- 事件详情：影响市场、关联板块 / 标的、来源链接
- 数据来自 `news_calendar_event`（财联社投资日历 + FOMC / BLS 固定日程导入）

### 4.8 研报 / 财报（并入个股详情）

研报与财报不再有独立中心页，统一并入个股详情右栏 tab（旧 `/research`、`/financial-reports` 重定向回工作台）：

| 维度 | 研报 tab | 财报 tab |
|------|----------|----------|
| 内容 | 个股相关研报列表 | 财报 PDF 列表（报告期 / 类型 / 券商 / 大小 / 下载次数） |
| PDF 下载 | 预签名 URL（`curl_cffi` 绕 WAF） | 预签名 URL |
| AI 摘要 | 查看缓存摘要 / AI 解读，缓存到 `file_metadata.summary` | 同上 |
| 采集触发 | 手动触发采集（返回 log_id 可查采集日志） | 同上 |

### 4.9 技能广场（/skills）

- **技能市场**：业务场景 Tab（全部 / 大盘与情绪 / 个股分析 / 产业链 / 财报与研报 / 资讯处理，枚举来自 `shared/types/skill.ts`）+ 名称 / ID 搜索；卡片展示能力徽标（自动化·定时 / 对话调用 / 方法论 / 自定义技能）与来源徽标（官方 / 自定义），点击整卡进入全页详情 `/skills/:skillId`（面包屑 + 元信息 + 文件树 + 内容预览），安装 / 卸载就地操作
- **我的技能**：已安装技能启用 / 停用（`PATCH /skills/{id}/install`）与卸载；自定义技能（配置非代码）创建 / 编辑 / 发布
- **上传解析**：创建表单支持上传标准 zip 压缩包（须含 SKILL.md），`POST /skills/analyze` 解析 frontmatter 自动预填（zip-slip / secret 防护）

### 4.10 个人设置

- **基本信息**：用户名 / 邮箱
- **行情配色**：涨跌配色方案开关（红涨绿跌 / 绿涨红跌），全站通过 `useColorScheme()` + formatters 自动应用；个股详情 ⚙ 图表设置弹层亦可即时切换
- **K 线均线**：用户级 MA 周期列表（存 `user.settings` JSONB 列），K 线组件订阅生效；**新注册账户默认启用 MA5 / MA10 / MA20 / MA60**
- **账号安全**：修改密码

### 4.11 后台管理（8 入口 + 代理配置）

| 页面 | 功能 |
|------|------|
| 总览 | ADMIN_LINKS 8 入口卡片 + 最近采集日志（「查看更多」跳采集管理） |
| 用户管理 | 列表 / 角色 / 启用 |
| 股票管理 | 列表 / 字段补全 / **同步任务入口** |
| 报告管理 | 存储统计卡片（`GET /admin/reports/storage-summary`，按 file_type 聚合 MinIO 文件数与字节数）+ 「清理 3 个月前报告」（二次确认，删 PDF 及存储对象）+ 研报 / 财报双 Tab 列表 |
| 资讯管理 | 列表 / 删除 |
| LLM 配置 | provider / base_url / api_key 加密存储 |
| MCP 服务 | `mcp_server_config` CRUD：HTTP(Streamable) / SSE / stdio 三通道动态表单 + 标准 `mcpServers` JSON 导入预填 + 连接测试（工具清单 / 可读错误）+ 启用注入开关（启用即注入 AI 助手，保存后自动重建 agent） |
| 分析结果 | skill Tabs（后端注册表驱动）+ 日期 / 状态筛选；「AI 重新生成」经侧边栏助手触发；删除为缓存清除语义（清空该业务键全部历史） |
| 采集管理 | 三合一 Tabs（与 `?tab=` 同步）：① 执行与日志（TASK_SPECS 目录任务按钮 + 最近日志）② 任务配置（`collector_task` CRUD，cron 中文展示）③ 渠道配置（渠道启用 + 数据类型优先级降级链） |
| 代理配置 | 采集出口代理 CRUD（HTTP / SOCKS5），仅侧边栏「后台管理」子菜单进入 |

## 5. 项目结构

```
web/
├── src/
│   ├── api/                    # API 请求层
│   ├── components/
│   │   ├── layout/             # Header / Sidebar / Layout / MobileTabBar
│   │   ├── charts/             # KlineChart / IndexKlineChart / IntradayChart / IntradaySpark /
│   │   │                       #   ChainGraph / FinancialTrendCharts / StockChartView / useKlineKeyboardNav
│   │   ├── assistant/          # assistant-ui 助手面板：RuntimeProvider / Thread / Composer / 会话侧栏
│   │   ├── common/             # Brand / MarkdownText / SourceNote
│   │   └── auth/               # ProtectedLayout / ProtectedAdmin / RedirectIfAuthenticated
│   ├── hooks/                  # TanStack Query 包装的 Hooks
│   ├── pages/                  # 见 §3 路由
│   ├── stores/                 # Zustand（auth / colorScheme / userSettings / assistant）
│   ├── test/                   # 测试环境初始化与 mocks
│   ├── types/ utils/ constants/ config/
│   ├── App.tsx / main.tsx / router.tsx
├── e2e/                        # Playwright E2E
├── index.html
├── package.json
└── ... 构建配置（vite / vitest / playwright / tsconfig）
```

## 6. 涨跌配色方案

涨跌色统一通过 formatters 中的 **scheme-aware helpers** 输出，组件用 `useColorScheme()` 订阅当前方案：

- **红涨绿跌**（国内习惯，默认）
- **绿涨红跌**（国际习惯）

切换在个人设置页完成，写入 `user.settings` JSONB 列，全站图表 / 数字 / 标签自动跟随。

## 7. 共享代码层（`shared/`）

```
shared/                       # 独立 npm 包，被 web 与 backend（uv）共享
├── api/
│   ├── endpoints.ts          # API 端点常量
│   └── index.ts
├── types/
│   ├── stock.ts / chain.ts / market.ts / admin.ts / api.ts / user.ts
└── utils/
    └── ...
```

## 8. Vite 构建配置

```typescript
// vite.config.ts
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
  base: '/',
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          charts: ['echarts', '@antv/g6', 'd3'],
          ui: ['antd', '@ant-design/icons'],
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000' },
    },
  },
})
```

SPA 静态托管（FastAPI 内置，`app/main.py` 的 `register_spa_routes`）：
- web-api 一体镜像为**单 uvicorn 进程直听 :9000**（无 nginx/supervisord），端口监听即完整服务，消除冷启动代理竞态 502
- 缓存语义：`/assets/` 长缓存（`max-age=31536000, immutable`，产物带内容哈希），`/index.html` 与 SPA 路由 fallback 禁止启发式缓存（发版后立即生效）
- HSTS / CSP `upgrade-insecure-requests` 仅 HTTPS 下发；`FORCE_FORWARDED_HTTPS=1`（SCF）强制 scheme=https，本地 http 访问不受影响
- API 未匹配路径保持 JSON 404，不落 index.html

## 9. 后续文档索引

- [00-overview.md](./00-overview.md) — 总体架构与目录结构
- [04-ai-agent.md](./04-ai-agent.md) — AI Agent 体系（前端如何调用版本化分析）
- [06-deployment.md](./06-deployment.md) — 部署方案
- [07-testing.md](./07-testing.md) — 测试体系
