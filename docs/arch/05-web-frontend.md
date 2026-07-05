# 前端架构设计（单镜像部署版）

## 1. 多端架构总览

系统提供 **Web 端 + 微信小程序** 双端访问能力，共享同一套后端 API。

```
                      用户
                       │
        ┌──────────────┴──────────────┐
        │                             │
   ┌────┴────┐                  ┌─────┴─────┐
   │ 浏览器   │                  │ 微信客户端  │
   │ (Web端) │                  │ (小程序端)  │
   └────┬────┘                  └─────┬─────┘
        │                             │
   HTTPS (API 网关)              HTTPS (wx.request)
        │                             │
   ┌────┴─────────────────────────────┴────┐
   │     腾讯云 SCF Web 函数                │
   │     Docker 镜像 (前后端合一)            │
   │                                       │
   │  Nginx :9000                          │
   │  ├── /       → React 静态资源 (Web端)  │
   │  ├── /api/*  → FastAPI :8000          │
   │  └── /ws/*   → WebSocket              │
   └───────────────────────────────────────┘
```

**Web 端** — 全功能投资分析平台（产业链图谱、K线、资金流向、研报等）

**小程序端** — 轻量级数据查看工具，聚焦移动端高频场景：
- 集合竞价可视化分析曲线
- 自选股实时行情
- 热点资讯速览
- AI 分析结果推送

## 2. Web 端技术栈

| 类别 | 技术 | 用途 |
|------|------|------|
| 框架 | React 18 + TypeScript | 主框架 |
| 构建 | Vite 5 | 开发/构建（输出至 `dist/`） |
| 状态管理 | Zustand | 轻量全局状态 |
| 路由 | React Router v6 | 页面路由 |
| UI 组件 | Ant Design 5 | 基础组件库 |
| K线图 | ECharts + echarts-for-react | 行情可视化 |
| 产业链图 | AntV/G6 v5 | 图谱可视化 |
| 资金流向 | D3.js | 桑基图/流向图 |
| 表格 | AG-Grid | 大数据量表格 |
| HTTP | Axios + React Query (TanStack) | 数据请求/缓存 |
| WebSocket | Socket.IO | 实时行情推送 |
| 认证 | JWT + React Context | 登录态管理 |
| 测试 | Vitest + Playwright | 单元/E2E 测试 |

## 3. 微信小程序端技术栈

| 类别 | 技术 | 用途 |
|------|------|------|
| 框架 | Taro 4.x (React 语法) | 跨端开发，可使用 Web 端组件 |
| UI 组件 | Taro UI / NutUI | 小程序原生风格组件库 |
| 图表 | ECharts for 小程序 (ec-canvas) | 集合竞价曲线、K线缩略图 |
| 状态管理 | Zustand (适配 Taro) | 与 Web 端共享状态逻辑 |
| HTTP | Taro.request | 微信小程序网络请求 |
| 认证 | wx.login + JWT | 微信登录 + 后端 JWT |
| 构建 | Taro CLI | 编译为微信小程序代码 |

> **选型理由**：Taro 允许用 React 语法编写小程序，Web 端的大量 hooks、类型定义、API 客户端可直接复用。`ec-canvas` 是 ECharts 官方的小程序版本，集合竞价曲线、K 线缩略图可直接渲染。

## 4. Web 端页面路由

```
/login                          # 登录页
/register                       # 注册页

/                               # 首页（仪表盘）
├── /dashboard                  # 数据看板总览
│   ├── /market                 # 市场总览
│   └── /watchlist              # 我的自选

├── /chain                      # 产业链分析
│   ├── /:industry              # 行业产业链全景
│   ├── /compare                # 产业链对比
│   └── /breakthrough           # 突破点追踪

├── /stock/:code                # 个股详情
│   ├── /financial              # 财务分析
│   ├── /research               # 研报汇总
│   ├── /kline                  # K线分析
│   └── /news                   # 相关新闻

├── /hotspot                    # 热点追踪
│   ├── /news                   # 新闻聚类
│   ├── /sentiment              # 市场情绪
│   └── /capital-flow           # 资金流向

├── /research                   # 研报中心
│   ├── /latest                 # 最新研报
│   ├── /:broker                # 按券商筛选
│   └── /rating-changes         # 评级变化

└── /settings                   # 用户设置
    ├── /profile                # 个人资料
    └── /watchlist-manage       # 管理自选
```

## 5. 小程序端页面设计

```
底部 TabBar
├── 🏠 首页 (index)
│   ├── 大盘概览（上证/深证/创业板指数卡片）
│   ├── 今日热点（3-5 条摘要）
│   └── 产业链突破点速报
│
├── 📈 行情 (market)
│   ├── 自选股列表（实时价格、涨跌幅）
│   ├── 集合竞价可视化分析（核心功能）
│   │   ├── 竞价价格曲线 (ec-canvas)
│   │   ├── 匹配量柱状图
│   │   └── 未匹配量 / 虚拟撮合
│   └── 个股 K 线缩略图
│
├── 🤖 AI 分析 (ai)
│   ├── AI 分析报告列表
│   ├── 产业链分析摘要
│   └── 研报观点速览
│
└── 👤 我的 (profile)
    ├── 用户信息
    ├── 自选股管理
    ├── 关注行业设置
    └── 消息通知设置
```

### 5.1 集合竞价可视化页面（小程序核心）

```
┌──────────────────────────────────────┐
│  ← 集合竞价                  分享    │
├──────────────────────────────────────┤
│                                      │
│   [股票搜索] 平安银行 000001  ▼       │
│                                      │
│   ┌──── 竞价信息卡片 ────────────┐   │
│   │  匹配价: 12.35  ↑ +2.3%      │   │
│   │  匹配量: 125,600 手          │   │
│   │  未匹配买单: 38,200 手       │   │
│   │  未匹配卖单: 12,500 手       │   │
│   └──────────────────────────────┘   │
│                                      │
│   ┌──── 竞价价格曲线 ────────────┐   │
│   │  ec-canvas 折线图             │   │
│   │                               │   │
│   │  价格                         │   │
│   │  12.4│        ╱────           │   │
│   │  12.3│    ╱──                 │   │
│   │  12.2│╱──                    │   │
│   │      └──────────────────     │   │
│   │      9:15  9:20  9:25  时间  │   │
│   └──────────────────────────────┘   │
│                                      │
│   ┌──── 匹配量柱状图 ────────────┐   │
│   │  ▓▓▓▓▓▓░░░░  (已匹配)        │   │
│   │  ░░░░▓▓▓▓▓▓  (未匹配买单)    │   │
│   │  ░░░░░░░░▓▓  (未匹配卖单)    │   │
│   │  9:15   9:20   9:25          │   │
│   └──────────────────────────────┘   │
│                                      │
│   ┌──── 买一卖一明细 ────────────┐   │
│   │  买一 12.34  15,200手        │   │
│   │  卖一 12.36   8,300手        │   │
│   │  昨收 12.07                  │   │
│   └──────────────────────────────┘   │
└──────────────────────────────────────┘
```

## 6. 小程序核心组件

### 6.1 集合竞价曲线组件

```tsx
// miniapp/src/components/AuctionChart.tsx
import { useEffect, useState } from 'react';
import Taro, { useDidShow } from '@tarojs/taro';
import { View } from '@tarojs/components';
import * as echarts from 'echarts/core';
// ec-canvas 是 ECharts 的小程序封装
import EcCanvas from '@/components/ec-canvas';

interface AuctionPoint {
  time: string;
  price: number;
  matchVol: number;
  bidVol: number;
  askVol: number;
}

export function AuctionChart({ stockCode }: { stockCode: string }) {
  const [data, setData] = useState<AuctionPoint[]>([]);

  useDidShow(() => {
    fetchAuctionData(stockCode);
  });

  const fetchAuctionData = async (code: string) => {
    const res = await Taro.request({
      url: `${API_BASE}/api/v1/stocks/${code}/auction`,
      header: { Authorization: `Bearer ${getToken()}` },
    });
    setData(res.data.points);
  };

  const getOption = () => ({
    grid: { top: 20, right: 20, bottom: 30, left: 50 },
    xAxis: {
      type: 'category',
      data: data.map(d => d.time),
    },
    yAxis: [
      { type: 'value', name: '价格', axisLabel: { formatter: '{value}' } },
      { type: 'value', name: '量(手)' },
    ],
    series: [
      {
        name: '匹配价', type: 'line', data: data.map(d => d.price),
        smooth: true, lineStyle: { color: '#1890ff', width: 2 },
        itemStyle: { color: '#1890ff' },
      },
      {
        name: '匹配量', type: 'bar', yAxisIndex: 1,
        data: data.map(d => d.matchVol),
        itemStyle: { color: 'rgba(24,144,255,0.3)' },
      },
    ],
  });

  return (
    <View className="auction-chart">
      <EcCanvas
        canvasId="auction-canvas"
        ec={echarts}
        option={getOption()}
      />
    </View>
  );
}
```

### 6.2 自选股实时行情列表

```tsx
// miniapp/src/pages/market/index.tsx
import { View, ScrollView } from '@tarojs/components';
import { useRealtimeQuote } from '@/hooks/useRealtimeQuote';

export default function MarketPage() {
  const { quotes } = useRealtimeQuote(watchlist);

  return (
    <ScrollView className="market-page">
      {watchlist.map(stock => {
        const q = quotes[stock.code];
        return (
          <View
            key={stock.code}
            className="stock-item"
            onClick={() => Taro.navigateTo({
              url: `/pages/auction/index?code=${stock.code}`
            })}
          >
            <View className="stock-name">{stock.name}</View>
            <View className="stock-code">{stock.code}</View>
            <View className={`stock-price ${q?.changePct > 0 ? 'up' : 'down'}`}>
              {q?.price?.toFixed(2)}
            </View>
            <View className={`stock-change ${q?.changePct > 0 ? 'up' : 'down'}`}>
              {q?.changePct > 0 ? '+' : ''}{q?.changePct?.toFixed(2)}%
            </View>
          </View>
        );
      })}
    </ScrollView>
  );
}
```

## 7. 小程序认证流程

```
小程序端                         后端 API
   │                              │
   ├── wx.login() ───────────────→│
   │  获取临时 code                │
   │                              │
   ├── POST /api/v1/auth/wx-login │
   │   { code }                   │
   │                              ├── 调用微信 API 换取 openid
   │                              ├── 查询/创建用户
   │←── { access_token,           │
   │      refresh_token,          │
   │      user_info }             │
   │                              │
   ├── 存储 token 到本地          │
   │                              │
   ├── 后续请求带 Authorization ──→│  JWT 校验
```

## 8. 多端共享层

```
shared/                       # Web 与小程序共享代码
├── api/
│   ├── client.ts             # API 客户端（适配 axios / Taro.request）
│   ├── stock.ts              # 股票数据接口
│   └── auth.ts               # 认证接口
├── types/
│   ├── stock.ts              # 类型定义
│   ├── chain.ts
│   └── api.ts
├── utils/
│   ├── formatters.ts         # 数字/日期格式化
│   └── constants.ts
└── hooks/
    ├── useAuth.ts            # 认证 hook（适配两端）
    └── useDebounce.ts
```

## 9. Vite 构建配置

```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') },
  },
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
      '/ws': { target: 'ws://127.0.0.1:8000', ws: true },
    },
  },
});
```

## 10. Taro 小程序配置

```typescript
// miniapp/config/index.ts
import { defineConfig } from '@tarojs/cli';

export default defineConfig({
  projectName: 'ai-invest-miniapp',
  date: '2026-07-05',
  designWidth: 750,
  deviceRatio: {
    640: 2.34 / 2,
    750: 1,
    828: 1.81 / 2,
  },
  sourceRoot: 'src',
  outputRoot: 'dist',
  plugins: [],
  defineConstants: {
    API_BASE: '"https://api.your-domain.com"',
  },
  copy: {
    patterns: [
      { from: 'src/components/ec-canvas/', to: 'dist/components/ec-canvas/' },
    ],
  },
  mini: {
    postcss: {
      pxtransform: { enable: true },
      url: { enable: true, config: { limit: 1024 } },
    },
    webpackChain(chain) {
      // 共享目录 alias
      chain.resolve.alias.set('@shared', path.resolve(__dirname, '../../shared'));
    },
  },
});
```

## 11. Web 端核心页面

### 11.1 产业链全景图（核心页面）

```
┌──────────────────────────────────────────────────────────────┐
│  [行业选择器 ▼]  半导体  ▼   [时间范围]  [分析模式 ▼]       │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────── 产业链关系图谱 (G6) ────────────────┐    │
│  │                                                       │    │
│  │    [硅材料] ──→ [晶圆制造] ──→ [芯片设计] ──→ [...] │    │
│  │      │            │             │                    │    │
│  │      ▼            ▼             ▼                    │    │
│  │   [设备商]    [封装测试]    [终端应用]                │    │
│  │                                                       │    │
│  │   ● 节点大小 = 营收规模                               │    │
│  │   ● 颜色深浅 = 毛利率水平                             │    │
│  │   ● 连线粗细 = 业务关联强度                           │    │
│  └───────────────────────────────────────────────────────┘    │
│                                                               │
├──────────────────────────┬────────────────────────────────────┤
│  左侧：节点详情面板       │  右侧：关键指标                   │
│                          │                                    │
│  选中节点：晶圆制造       │  行业毛利率走势图 (ECharts)        │
│  代表公司：              │  ┌────────────────────────────┐   │
│  ● 中芯国际 (688981)    │  │  ▁▂▃▄▅▆▇███▇▆▅▄▃▂▁        │   │
│  ● 华虹半导体 (688347)  │  │  2020  2021  2022  2023     │   │
│  ● 晶合集成 (688249)    │  └────────────────────────────┘   │
│                          │                                    │
│  平均毛利率：28.5%       │  资金流向 (桑基图)                 │
│  同比增长：+3.2%         │  ┌────────────────────────────┐   │
│  议价能力：★★★★☆        │  │ 主力 ──→ 晶圆制造           │   │
│  [查看详细分析 →]        │  │ 游资 ──→ 芯片设计           │   │
│                          │  └────────────────────────────┘   │
└──────────────────────────┴────────────────────────────────────┘
```

### 11.2 资金流向页

```
┌──────────────────────────────────────────────────────────────┐
│  资金流向监控                            [日期选择器 ▼ 今天] │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ 主力净流入    │  │ 北向资金      │  │ 融资融券          │   │
│  │  +125.6亿     │  │  +38.2亿      │  │ 余额: 15,823亿   │   │
│  │  ↑ 12.3%      │  │  ↑ 5.1%       │  │ ↑ 0.8%           │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
│                                                               │
│  ┌──── 资金流向桑基图 (D3.js) ───────────────────────────┐   │
│  │  [主力] ──────┬──→ [半导体] 28.5亿                     │   │
│  │               ├──→ [新能源] 22.1亿                     │   │
│  │               └──→ [医药]   18.3亿                     │   │
│  │  [游资] ──────┬──→ [AI概念] 12.6亿                    │   │
│  └─────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### 11.3 热点追踪页

```
┌──────────────────────────────────────────────────────────────┐
│  热点追踪                              [刷新] [自动刷新: 5min]│
├──────────────────────────────────────────────────────────────┤
│  热点话题云: AI芯片 🟢  固态电池 🟢  机器人 🟡  低空经济 🟡  │
│                                                               │
│  最新热点新闻（时间线）                                       │
│  14:32 [AI芯片] 英伟达发布新一代GPU，算力提升300%            │
│  14:15 [固态电池] 宁德时代固态电池通过车规认证               │
│                                                               │
│  🚀 产业链突破点追踪                                         │
│  半导体设备：国产5nm刻蚀机交付，打破海外垄断                  │
│  AI算力：华为昇腾910C量产，性能比肩H100                      │
└──────────────────────────────────────────────────────────────┘
```

## 12. Web 端项目结构

```
web/
├── public/
│   └── favicon.ico
├── src/
│   ├── api/                    # API 请求层
│   │   ├── client.ts           # Axios 实例（JWT 拦截器）
│   │   ├── stock.ts            # 股票相关 API
│   │   ├── chain.ts            # 产业链 API
│   │   ├── research.ts         # 研报 API
│   │   └── auth.ts             # 认证 API
│   ├── components/             # 通用组件
│   │   ├── layout/             # 布局 (Header/Sidebar/Content)
│   │   ├── charts/             # 图表 (KlineChart/ChainGraph/SankeyChart)
│   │   ├── common/             # 通用 (StockSelector/DateRangePicker)
│   │   └── auth/               # 认证 (LoginForm/RegisterForm)
│   ├── hooks/                  # Hooks
│   ├── pages/                  # 页面
│   │   ├── Dashboard/  ChainAnalysis/  StockDetail/
│   │   ├── Hotspot/   CapitalFlow/    Research/
│   │   ├── Login/     Settings/
│   ├── stores/                 # Zustand 状态
│   ├── types/                  # 类型定义
│   ├── utils/                  # 工具函数
│   ├── App.tsx / main.tsx / router.tsx
├── index.html
├── package.json / tsconfig.json / vite.config.ts
└── .env.production
```

## 13. 小程序端项目结构

```
miniapp/
├── config/
│   └── index.ts                # Taro 构建配置
├── src/
│   ├── pages/
│   │   ├── index/              # 首页（大盘概览）
│   │   ├── market/             # 行情页（自选股列表入口）
│   │   ├── auction/            # 集合竞价可视化（核心）
│   │   ├── ai/                 # AI 分析报告
│   │   └── profile/            # 个人中心
│   ├── components/
│   │   ├── ec-canvas/          # ECharts 小程序封装
│   │   ├── AuctionChart.tsx    # 竞价曲线组件
│   │   ├── StockCard.tsx       # 股票卡片
│   │   └── HotNewsCard.tsx     # 热点新闻卡片
│   ├── hooks/
│   │   ├── useAuth.ts          # 微信登录 hook
│   │   ├── useRealtimeQuote.ts # 实时行情
│   │   └── useAuctionData.ts   # 竞价数据
│   ├── utils/
│   │   ├── request.ts          # Taro.request 封装
│   │   └── auth.ts             # Token 管理
│   ├── app.config.ts           # 小程序全局配置
│   ├── app.tsx                 # 小程序入口
│   └── app.scss
├── project.config.json         # 微信小程序项目配置
├── package.json
└── tsconfig.json
```

## 14. 共享代码层

```
shared/
├── api/
│   ├── types.ts                # API 响应类型
│   └── endpoints.ts            # API 端点常量
├── types/
│   ├── stock.ts                # 股票数据结构
│   ├── chain.ts                # 产业链数据结构
│   └── auction.ts              # 集合竞价数据结构
└── utils/
    ├── formatters.ts           # 金额/百分比格式化
    └── constants.ts            # 行业分类/市场枚举
```
