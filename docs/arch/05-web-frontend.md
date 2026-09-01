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
│ React SPA（nginx 静态）· /assets/ 长缓存   │
│ FastAPI /api/* 同源 · 代理超时 300s（LLM） │
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
/login                          # 登录页（OAuth2 表单，首个注册用户自动晋升管理员）
/register                       # 注册页

/workbench                      # 工作台（登录后默认入口：日历摘要 / 复盘结论 / 要闻 / 自选股概览 / 市场快览）
/                               # 每日复盘（Dashboard）
├── /chain/:industry?           # 产业链分析（带行业参数，支持版本切换）
├── /stock/:code                # 个股详情（同花顺风格多周期 K 线 + 财务 tab）
├── /hotspot                    # 热点追踪
├── /capital-flow               # 资金流向（板块河流图 + 排名图）
├── /auction                    # 集合竞价（指数成交额趋势）
├── /calendar                   # 投资日历（月历 / 周历 / 列表三视图，分类筛选）
├── /research                   # 研报中心（筛选 / PDF / AI 摘要）
├── /financial-reports          # 财报中心（采集 / 列表 / AI 摘要）
├── /financial/:code            # 财务体检详情（独立入口，也嵌入个股 Tab）
└── /settings                   # 个人设置（基本信息 / 配色 / K 线均线 / 安全）

/admin                          # 后台管理总览
├── /admin/users                # 用户管理
├── /admin/stocks               # 股票管理（含列表同步任务入口）
├── /admin/reports              # 研报管理
├── /admin/news                 # 资讯管理
├── /admin/tasks                # 采集任务管理（collector_task 调度行 CRUD，cron 中文展示）
├── /admin/llm-configs          # LLM 配置
├── /admin/collector-channels   # 采集渠道管理（渠道启用 + 数据类型优先级）
├── /admin/tracked-index        # 跟踪指数管理（大盘页/工作台指标清单，全局动态可配）
└── /admin/collector            # 采集任务（TASK_SPECS 目录驱动：任务清单/标签/状态 + 手动执行）
```

> 侧边栏按"复盘 / 分析 / 设置"三大组分组，移动端折叠为底部 Tab Bar。

## 4. 核心页面

### 4.1 工作台（登录默认入口）

卡片化聚合页（`/workbench`，登录后默认路由；每日复盘保留为独立页，侧边栏入口不变）：

| 模块 | 内容 |
|------|------|
| 投资日历摘要 | 近 7 日关键事件，点击进入完整日历 |
| 复盘核心结论 | AI 大盘综述分区摘要 + 涨停情绪概要（链接至每日复盘页） |
| 要闻资讯 | 重要新闻 / 公告流（按重要性排序） |
| 自选股概览 | 自选股行情卡 + 当日 AI 每日分析摘要（三段式） |
| 市场快览 | 跟踪指数与全球指标实时卡片（清单由后台"跟踪指数管理"配置） |

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
│  [行情头：现价 / 涨跌 / 成交]  [加入自选 ♥]                  │
├──────────────────────────────────────────────────────────────┤
│  Tabs: K 线 │ 财务 │ 研报 │ 板块归属 │ AI 每日分析            │
├──────────────────────────────────────────────────────────────┤
│  K 线 Tab：多周期预设（日+周 / 日 + 月 / 仅日 / 仅周）       │
│   ┌──────────── K 线图（键盘缩放 / 平移） ──────────────┐   │
│   │  默认可视 bar 数可配置                                │   │
│   └──────────────────────────────────────────────────────┘   │
│                                                               │
│  财务 Tab：                                                  │
│   - 当期财务体检评分（毛利率 / 净利率 / ROE / 资产负债率）   │
│   - 近 8 期历史趋势图（FinancialTrendCharts）                │
│                                                               │
│  板块归属 Tab：行业 + 概念板块（基于 mapping_stock_concept） │
│                                                               │
│  AI 每日分析 Tab：盘面解读 / 操作策略 / 止损线（盘后定时生成）│
│   固定附"AI 生成，不构成投资建议"免责声明                     │
└──────────────────────────────────────────────────────────────┘
```

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
- 数据来自 `calendar_event`（财联社投资日历 + FOMC / BLS 固定日程导入）

### 4.8 研报 / 财报中心

| 维度 | 研报中心 | 财报中心 |
|------|----------|----------|
| 路由 | `/research` | `/financial-reports` |
| 筛选 | 券商 / 行业 / 评级 / 时间 | 报告类型 / 时间 |
| PDF 下载 | 预签名 URL（`curl_cffi` 绕 WAF） | 预签名 URL |
| AI 摘要 | `POST /research/{id}/summarize`，缓存到 `file_metadata.summary` | 同上 |
| 采集触发 | 后台任务管理 | 列表页 `CollectModal`，返回 log_id 可查采集日志 |

### 4.9 个人设置

- **基本信息**：用户名 / 邮箱
- **行情配色**：涨跌配色方案开关（红涨绿跌 / 绿涨红跌），全站通过 `useColorScheme()` + formatters 自动应用
- **K 线均线**：用户级 MA 周期列表（保存到 `user_settings`），K 线组件订阅生效
- **账号安全**：修改密码

### 4.10 后台管理（10 个子页）

| 页面 | 功能 |
|------|------|
| 总览 | 系统状态 / 最近任务 |
| 用户管理 | 列表 / 角色 / 启用 |
| 股票管理 | 列表 / 字段补全 / **同步任务入口** |
| 研报管理 | 列表 / 名称展示 |
| 资讯管理 | 列表 / 删除 |
| 采集任务管理 | `collector_task` 调度行 CRUD（任务 / 渠道 / cron 中文展示 / 启用） |
| LLM 配置 | provider / base_url / api_key 加密存储 |
| 采集渠道管理 | 渠道启用 / base_url / api_key / extra + 数据类型优先级 |
| 跟踪指数管理 | `tracked_index_config` 全局指标清单维护（新增 / 删除 / 排序 / 启停），大盘页与工作台共用 |
| 采集任务 | TASK_SPECS 目录驱动只读清单（label / 渠道 / 队列 / 最近执行）+ 手动执行 + 采集日志 |

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

切换在个人设置页完成，写入 `user_settings`，全站图表 / 数字 / 标签自动跟随。

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

Nginx 配置（`docker/web/nginx.conf`）：
- nginx（web-api 一体镜像）对 SPA 静态资源采用缓存语义：`/assets/` 长缓存（`max-age=31536000, immutable`，产物带内容哈希），`/index.html` 禁止启发式缓存（发版后立即生效）
- `/api/` 代理超时 300s（LLM 调用可达 1-2 分钟）

## 9. 后续文档索引

- [00-overview.md](./00-overview.md) — 总体架构与目录结构
- [04-ai-agent.md](./04-ai-agent.md) — AI Agent 体系（前端如何调用版本化分析）
- [06-deployment.md](./06-deployment.md) — 部署方案
- [07-testing.md](./07-testing.md) — 测试体系
