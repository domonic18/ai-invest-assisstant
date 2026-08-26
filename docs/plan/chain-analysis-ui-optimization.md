# 产业链分析页面 UI/UX 优化方案

## 背景与用户反馈

当前产业链分析页面已实现 Skill 驱动的 Agent 分析流程与基础图谱交互（缩放、过滤、搜索、小地图）。但在实际使用中，用户反馈 6 个 UI/UX 问题：

1. 整体页面为深色主题，但产业链图谱仍是白色背景，视觉突兀。
2. 白色背景导致顶部工具栏看不清（白色文字/图标被遮盖），且工具栏样式不精致。
3. 图谱小地图单独显示在主画布下方，不符合行业常见的右下角悬浮面板习惯。
4. 页面上方「图谱版本」「产业链关系图谱」文字区域占用过多垂直空间。
5. 下方「毛利率 × 国产化率矩阵」「价值分布」在数据不足时仍显示大片空白，不美观。
6. 下方「瓶颈与卡脖子风险」「机会」「风险」「核心标的」展示缺乏逻辑与布局美感，需参照行业最佳实践重构。

## 设计目标

- 让产业链图谱完全融入现有深色主题，与页面其他图表风格一致。
- 工具栏精致化：深色半透明玻璃态、图标清晰、分组明确。
- 小地图改为画布右下角悬浮。
- 压缩头部空间，减少无效标题与留白。
- 无内容卡片自动收缩/隐藏，避免空白占位。
- 底部洞察区采用统一的卡片/标签页布局，信息层级清晰。

## 现状梳理

- 全局深色主题：`web/src/App.tsx` 使用 `theme.darkAlgorithm`；`web/src/index.css` body 背景 `#0c0e12`。
- 已有色板：`web/src/theme/colors.ts` 提供 `panelColors`（bg `#0c0e12`、border `#23262e`、textMuted `#8c8c8c`）。
- 图表暗色规范：ECharts 组件已统一使用 `backgroundColor: 'transparent'`，轴/网格颜色 `#8c8c8c` / `#3a3f4b` / `rgba(255,255,255,0.06)`。
- 例外：`ChainGraph` 与 `chainGraphStyle.ts` 仍按浅色画布硬编码（节点白底、文字深灰、分栏条浅蓝/浅绿）。
- 底部组件：`QuadrantMatrix`、`ValueDistributionCard`、`BottleneckPanel`、`KeyCompaniesPanel` 已存在，但缺乏空状态收缩与统一布局。

## 推荐方案

### 1. 图谱深色化（ChainGraph + chainGraphStyle）

#### 1.1 颜色规范

基于现有暗色主题，统一使用以下颜色（不新增 token，直接复用常量）：

| 元素 | 颜色 |
|------|------|
| 画布背景 | `transparent`（外层容器为 `#0c0e12` 或 `#14161c`） |
| 节点填充 | `#1a1d24` |
| 节点描边 | 上游 `#3b82f6`、中游 `#6366f1`、下游 `#10b981`（保持原色，因深色下仍清晰） |
| 节点标题/主文字 | `#d1d4dc` |
| 节点次要文字 | `#8c8c8c` |
| 分隔线 | `#23262e` |
| 分栏条背景 | 上游 `rgba(59,130,246,0.12)`、中游 `rgba(99,102,241,0.12)`、下游 `rgba(16,185,129,0.12)` |
| 分栏条文字 | 对应原色 `#3b82f6` / `#6366f1` / `#10b981` |
| 边颜色 | high `#6366f1`、medium `#8c8c8c`、low `rgba(255,255,255,0.2)` |
| 高亮描边 | `#2563eb` + 阴影 `rgba(37,99,235,0.4)` |
| 信号徽章背景 | 突破 `rgba(239,68,68,0.12)`、瓶颈 `rgba(217,153,34,0.12)` |
| 信号徽章文字 | 突破 `#ef4444`、瓶颈 `#d29922` |

#### 1.2 文件改动

- `web/src/components/charts/chainGraphStyle.ts`
  - 将 `BAND_STYLES` 改为深色半透明填充。
  - 将 `buildSignalBadges` 的填充色改为半透明深色背景。
  - 将 `edgeStyleByCriticality` 的 low 颜色从浅灰改为 `rgba(255,255,255,0.2)`。
- `web/src/components/charts/ChainGraph.tsx`
  - 外层容器背景从 `#fafbfc` 改为 `#14161c`（或 `bg-panel-bg`）。
  - 节点绘制中：box fill `#1a1d24`、主文字 `#d1d4dc`、次要文字 `#8c8c8c`、分隔线 `#23262e`。
  - 调整 `nodeStateStyles.dim` 与 `highlight`，确保深色下可见。
  - 为 minimap 容器设置深色背景与边框。

### 2. 工具栏精致化（ChainGraphToolbar）

#### 2.1 视觉方案

- 使用深色半透明玻璃态容器：
  - 背景 `rgba(20,22,28,0.85)`
  - 边框 `1px solid #23262e`
  - 圆角 `8px`
  - 阴影 `0 4px 12px rgba(0,0,0,0.3)`
  - 文字/图标颜色 `#d1d4dc`，Hover 背景 `rgba(255,255,255,0.08)`
- 分组更清晰：
  - 第一组：缩放/适配/全屏（图标按钮）
  - 第二组：节点类型过滤（上游/中游/下游，使用 AntD `Checkbox`）
  - 第三组：边关键性过滤（全部/高/中/低，使用 AntD `Segmented` 替代 Radio.Group，更紧凑）
  - 第四组：搜索框（深色背景）
- 各组之间使用 `1px #23262e` 竖线分隔。

#### 2.2 文件改动

- `web/src/components/charts/ChainGraphToolbar.tsx`
  - 替换外层 `div` 样式为玻璃态暗色。
  - 图标按钮统一使用 `w-7 h-7`、圆角、hover 态。
  - 边关键性改用 `Segmented`。
  - 搜索框使用 AntD `Input.Search`，背景 `#0c0e12`，边框 `#23262e`。

### 3. 小地图悬浮右下角

#### 3.1 实现方式

G6 Minimap 会创建一个 class 为 `chain-graph-minimap` 的 DOM。通过全局 CSS（写入 `web/src/index.css` 或组件 scoped CSS）将其绝对定位到图谱容器右下角：

```css
.chain-graph-minimap {
  position: absolute !important;
  right: 12px;
  bottom: 12px;
  width: 160px;
  height: 100px;
  background: rgba(20, 22, 28, 0.85);
  border: 1px solid #23262e;
  border-radius: 8px;
  overflow: hidden;
  z-index: 10;
}
```

确保 `.chain-graph-minimap canvas` 显示完整，无额外滚动条。

#### 3.2 文件改动

- `web/src/index.css`：新增上述 `.chain-graph-minimap` 样式。
- 备选：在 `ChainGraph.tsx` 同级新增 `ChainGraph.css` 并通过 `import` 引入，避免污染全局。

### 4. 压缩页面头部空间

#### 4.1 改动点

- 移除 `ChainGraph` 外 `Card` 的 `title="产业链关系图谱"`，或改为更小的二级标题 inline 在工具栏右侧/上方。
- `VersionSwitcher` 保持，但减少内边距（`py-2` 替代 `py-3`），选择器宽度从 `300px` 改为 `240px`。
- 标题区与操作区保持 `justify-between`，但减少 `space-y-6` 的间距，可改为 `space-y-4`。
- 版本号 tag 与标题放在同一行，减小字号。

#### 4.2 文件改动

- `web/src/pages/ChainAnalysis/ChainAnalysis.tsx`
  - 调整外层间距。
  - 给 `ChainGraph` 外 `Card` 移除 title，或改为轻量 header。
- `web/src/pages/ChainAnalysis/components/VersionSwitcher.tsx`
  - 紧凑化 padding 与选择器宽度。

### 5. 空状态卡片收缩

#### 5.1 处理策略

- **QuadrantMatrix**：当 `points.length === 0` 时，不再显示 `h-72` 的占位，而是返回 `null`，由调用方控制是否渲染整个 `Card`。
- **ValueDistributionCard**：当 `ranked.length === 0` 且 `valueDistribution` 全为空时返回 `null`。
- **ChainAnalysis.tsx**：在渲染矩阵/价值分布卡片前判断数据是否存在；无数据时整行不渲染。

#### 5.2 文件改动

- `web/src/pages/ChainAnalysis/components/QuadrantMatrix.tsx`：空状态返回 `null`。
- `web/src/pages/ChainAnalysis/components/ValueDistributionCard.tsx`：空状态返回 `null`。
- `web/src/pages/ChainAnalysis/ChainAnalysis.tsx`：条件渲染矩阵与价值分布卡片。

### 6. 底部洞察区重构

#### 6.1 布局方案

采用「左侧主洞察 + 右侧核心标的」两栏布局（`xl:grid-cols-3`，左侧占 2 列，右侧占 1 列），将瓶颈、机会、风险整合为标签页卡片；核心标的单独列为右侧竖向列表。

结构：

```
┌──────────────────────────────┬──────────────┐
│  洞察聚合（Tabs）             │  核心标的     │
│  ┌─机会─┬─风险─┬─瓶颈─┐       │  评分列表     │
│  │ 卡片列表                    │              │
│  └───────────────────────────┘              │
└──────────────────────────────┴──────────────┘
```

#### 6.2 洞察卡片设计

每个机会/风险/瓶颈项使用统一卡片：

- 顶部：标题 + 置信度/严重度 Tag（high/medium/low 映射为红/琥珀/灰）+ 相关环节 Tag。
- 中部：描述文字，限制最多 3 行。
- 底部：若为风险/机会，可显示「影响环节」小字。

统一使用 AntD `Badge` 或左侧色条区分类型：
- 机会：左侧色条 `#10b981`
- 风险：左侧色条 `#ef4444`
- 瓶颈：左侧色条 `#d29922`

#### 6.3 核心标的列表

- 使用紧凑列表，每项显示：排名序号、公司名称/代码、产业链位置 Tag、评分进度条。
- 评分进度条使用 AntD `Progress` 小号，颜色 `#6366f1`。
- 最多显示 Top 10，超出折叠。

#### 6.4 文件改动

- 新增 `web/src/pages/ChainAnalysis/components/InsightTabs.tsx`
  - 接收 `opportunities`、`risks`、`bottlenecks`（从 nodes 提取）。
  - 使用 AntD `Tabs` 组织三栏。
  - 每个 tab 内部使用统一卡片组件渲染列表。
- 新增 `web/src/pages/ChainAnalysis/components/InsightCard.tsx`（可选内联）
  - 统一的 item 展示组件。
- 重构 `web/src/pages/ChainAnalysis/components/KeyCompaniesPanel.tsx`
  - 改为更紧凑的列表，带排名与评分。
- 重构 `web/src/pages/ChainAnalysis/components/BottleneckPanel.tsx`
  - 改为返回结构化数组，供 `InsightTabs` 使用；或直接移除，由 `InsightTabs` 接管瓶颈展示。
- `web/src/pages/ChainAnalysis/ChainAnalysis.tsx`
  - 使用新网格布局替换现有四卡片堆叠。

### 7. 节点详情面板适配

- `NodeDetailCard` 当前在绝对定位卡片内，保持现有行为。
- 适配深色：AntD `Card` 在 darkAlgorithm 下自动深色，无需额外改动；只需确保文字使用 `type="secondary"` 即可。

### 8. 响应式

- 工具栏在小屏幕下允许换行，保持可用。
- 底部洞察区在 `lg` 以下改为单栏堆叠。
- 图谱高度在 `isFullscreen` 时 `h-full`，非全屏保持 `h-[700px]`。

## 关键文件变更

### 修改
- `web/src/components/charts/chainGraphStyle.ts` — 深色化颜色常量。
- `web/src/components/charts/ChainGraph.tsx` — 深色节点绘制、画布背景、状态样式。
- `web/src/components/charts/ChainGraphToolbar.tsx` — 玻璃态深色工具栏、Segmented 过滤。
- `web/src/index.css`（或新增 `ChainGraph.css`）— minimap 右下角悬浮样式。
- `web/src/pages/ChainAnalysis/ChainAnalysis.tsx` — 紧凑头部、条件渲染矩阵/价值分布、洞察区新布局。
- `web/src/pages/ChainAnalysis/components/VersionSwitcher.tsx` — 紧凑化。
- `web/src/pages/ChainAnalysis/components/QuadrantMatrix.tsx` — 空状态返回 null。
- `web/src/pages/ChainAnalysis/components/ValueDistributionCard.tsx` — 空状态返回 null。
- `web/src/pages/ChainAnalysis/components/KeyCompaniesPanel.tsx` — 紧凑列表+排名。
- `web/src/pages/ChainAnalysis/components/BottleneckPanel.tsx` — 改为供 InsightTabs 使用的数据提取或移除。

### 新增
- `web/src/pages/ChainAnalysis/components/InsightTabs.tsx` — 机会/风险/瓶颈标签页聚合。
- 可选 `web/src/pages/ChainAnalysis/components/InsightCard.tsx` — 统一洞察项卡片。

## 验证

1. 类型检查：`cd web && npm run typecheck`
2. 代码质量：`cd web && npm run lint`
3. 单元测试：`cd web && npm run test:unit`
4. 构建验证：`cd web && npm run build`
5. 视觉验证：
   - 打开产业链页面，确认图谱背景为深色，节点文字清晰可见。
   - 确认工具栏为深色半透明，所有图标与文字清晰。
   - 确认小地图位于图谱右下角，不额外占行。
   - 确认头部标题/版本区紧凑。
   - 切换到一个缺少毛利率/国产化率数据的版本，确认矩阵/价值分布整卡隐藏。
   - 确认底部洞察区为 Tabs + 核心标的两栏布局，信息层级清晰。

## 决策说明

- **为什么把 minimap 用 CSS 绝对定位而不是 G6 配置**：G6 Minimap 本身只生成一个 DOM 容器，通过 CSS 定位最简单，不侵入 G6 内部渲染。
- **为什么空状态返回 `null` 而不是占位提示**：用户明确反感大片空白；隐藏无数据卡片能减少视觉噪音。
- **为什么底部用 Tabs 聚合机会/风险/瓶颈**：三者属于同类洞察信息，Tabs 能在同一区域切换，避免页面过度拉长；核心标的作为独立维度放在右侧，便于快速查看评分。
- **为什么不改 shared types / 后端**：本次为纯 UI 优化，数据结构与 API 已满足需求。
