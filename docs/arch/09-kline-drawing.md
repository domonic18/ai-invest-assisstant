# K 线画线与 AI 智能画线架构设计

> 闭环：用户在 K 线图绘制/管理画线（数据坐标锚定、实时落库）→ Agent 读画线（含文字标识）注入复盘与趋势分析 → 侧边栏对话触发 Agent 智能画线（画线前问题卡确认）→ AI 画线图层原位编辑与采纳。
> 需求：[docs/requirement/03-kline-drawing-requirement.md](../requirement/03-kline-drawing-requirement.md)（F-DRAW-01~08）· 原型：[docs/prototypes/kline-drawing.html](../prototypes/kline-drawing.html)

## 1. 设计原则

1. **锚点即契约**：画线锚点一律存数据坐标 `(date, price)`，像素坐标只在渲染瞬间存在。数据坐标使画线在新 K 线追加、缩放、跨周期渲染下语义稳定，也是 Agent 可结构化读写的前提——LLM 输出/读取的是同一套坐标语义，不是屏幕位置。
2. **图层与主图解耦**：画线层是独立模块（`components/charts/drawing/`），经 `DrawingLayerHost` 以组合方式接入个股/板块（StockChartView）与大盘指数（IndexKlineChart）两套图表组件；图层任何异常降级为「不渲染画线」，不侵入 K 线主图渲染与既有交互（十字光标/键盘导航/异动 markers）。
3. **用户画线与 AI 画线物理分表，均为 per-user 私有**：用户画线是用户资产（长期保留）；AI 画线是会话属主的私有可变工作区（多租户隔离，A 的 AI 画线对 B 不可见）。分表使二者的生命周期、权限、备份语义互不牵连。
4. **Agent 双向共用一套 wire 契约**：读（画线上下文序列化 + 查询工具）与写（persist 工具）走同一份 `shared/types` 画线类型，Pydantic schema 镜像同构；文字标识（标注文字 / label / reason）作为一等字段进入契约。
5. **写路径人工优先**：AI 画线仅由对话触发、画线前必须经问题卡确认；用户画线的删除 Agent 无权静默执行（二次确认）。

## 2. 渲染技术选型（评估结论）

| 方案 | 评估 | 结论 |
|------|------|------|
| **ECharts graphic + zrender 事件** | 画线元素（line/rect/text/circle）活在图表实例内，原生获得命中检测、拖拽（`draggable` + ondrag）、与十字光标同层渲染；`convertToPixel/convertFromPixel` 承担数据↔像素换算；代价是 dataZoom/resize 时需重算像素并增量更新 | **选定** |
| markLine / markArea | 数据坐标自动跟随缩放（免重算），但无交互能力（不可拖拽/选中）、样式受限、无法表达射线延伸与锚点手柄；仅继续用于既有异动日 markers | 复用既有用途 |
| 自绘 SVG/Canvas 覆盖层 | 与 ECharts 缩放/十字光标对齐需手工订阅全部视图事件，双坐标系长期维护成本高 | 弃 |
| klinecharts 换库 | 自带画线工具集，但需整图重写：既有 MA/指标体系、异动 markers、键盘导航、全屏、两套组件全部迁移 | 弃（成本收益不成比例） |

## 3. 前端架构

### 3.1 模块结构

```
web/src/components/charts/drawing/
├── types.ts              # re-export shared/types 画线类型（前端单一真相源）
├── coordinates.ts        # 纯函数：数据↔像素换算、bar 日期对齐、越界裁剪
├── geometry.ts           # 纯函数：射线延伸、锚点几何运算（geometry.test.ts 钉死）
├── chartInternals.ts     # ECharts 实例内部读取助手（grid / 坐标系）
├── shapeSpecs.ts         # 5 类型 → ECharts graphic 元素规格
├── draftMachine.ts       # 交互状态机（idle→armed→drafting→selected→dragging，纯函数测试）
├── layerEvents.ts        # dataZoom / resize / finished 视图联动与事件绑定
├── sessions.ts           # 绘制会话（草稿生命周期）
├── useDrawingLayer.ts    # 图层内部 hook：渲染/重定位/命中托管（render/interaction 测试钉死）
├── DrawingLayerHost.tsx  # 组合接入收口：两套图表经此挂载图层（对外唯一入口）
├── DrawingToolbar.tsx    # 画线模式开关 + 5 类型子工具条 + 图层显隐
├── DrawingSideBar.tsx    # 画线侧边工具条
├── StyleBar.tsx          # 选中浮动样式条（6 色/线型/线宽/文字/删除）
├── DrawingTextInput.tsx  # 文字标注输入
├── AiDrawingButton.tsx   # 「AI 画线」入口按钮
└── DrawingsPanel.tsx     # 画线清单面板（用户组 + AI 组：采纳/删除/来源徽标）
```

### 3.2 接入与坐标换算

- 两套图表组件均经 `echarts-for-react` 持有实例（`chartRef.current.getEchartsInstance()`），以 `<DrawingLayerHost>` 组合接入（内部再驱动 `useDrawingLayer` hook），不复制交互逻辑。
- x 轴为 category（bar 日期）：锚点 date 经 `geometry.buildDateIndex(bars)` 对齐到「≤ 该日期的最后一根 bar」，越界锚点裁剪在绘图区边缘；射线按两端锚点像素求方向向量延伸至 grid 右缘（`direction: left/right/both`）。
- 视图联动：订阅实例 `dataZoom` / `resize` / `finished` 事件，对每个画线重算像素后以同 id `setOption({graphic})` 增量更新（禁止整图 setOption，保拖拽帧率）。
- 交互状态机：`idle → armed(选工具) → drafting(拖拽草稿) → selected → dragging(anchor|move)`；armed 状态与 dataZoom 互斥（画线模式下滚轮/拖动不缩放），Delete 键删除选中项。

### 3.3 状态与数据流

- **服务端状态**：TanStack Query `['kline-drawings', targetType, targetCode]` 一次拉取该标的**全周期**画线（`GET` 返回按 period 分组的 user + ai 两组）；周期切换纯前端过滤——严格隔离由「period 是画线归属键的一部分」保证，切换零请求。
- **客户端状态**：zustand `drawingStore`（当前工具 / 选中项 / 样式条位置 / 默认样式记忆 localStorage per user）；变更即调 mutation（POST/PATCH/DELETE），乐观更新 + 失败回滚 toast。

## 4. wire 契约（shared/types/drawing.ts）

```ts
interface KlineDrawingAnchor { date: string; price: number }
interface KlineDrawingStyle { color: string; lineStyle: 'solid'|'dashed'|'dotted'; width: 1|2|3 }
interface UserKlineDrawing {
  id: string; targetType: 'stock'|'index'|'sector'; targetCode: string;
  period: 'daily'|'weekly'|'monthly'; drawingType: 'trendline'|'ray'|'hline'|'box'|'text';
  anchors: KlineDrawingAnchor[]; direction?: 'left'|'right'|'both';
  text?: string; style: KlineDrawingStyle;
}
interface AiKlineDrawingItem {
  drawingType: string; anchors: KlineDrawingAnchor[]; direction?: string;
  label: string; reason: string;
}
interface AiKlineDrawingGroup {
  targetType: string; targetCode: string; period: string;
  skillId: string; tradeDate: string; summary?: string; drawings: AiKlineDrawingItem[];
}
// GET /api/v1/kline-drawings → { user: UserKlineDrawing[]; ai: AiKlineDrawingGroup[] }
```

后端 Pydantic `CamelModel` 镜像同构（`app/schemas/drawing.py`）；AI 图层颜色/线型由前端固定渲染，不进契约。

## 5. 数据模型

| 表 | 键与约束 | 说明 |
|----|----------|------|
| `user_kline_drawing` | idx `(user_id, target_type, target_code, period)`；每行一条画线 | `payload JSONB`（anchors + direction + style + text）；审计字段 `created_at/updated_at` |
| `ai_kline_drawing` | uq `(user_id, target_type, target_code, period)`；每用户每标的每周期一套画线集 | `user_id` 归属（多租户隔离）+ `drawings JSONB` 数组（label 组内唯一）+ `skill_id`（最近来源）+ `trade_date`（最近生成日）+ `summary`；可变工作区，人工原位编辑直接更新 |

- 迁移：`docker/database/migrations/<date>_kline_drawing.sql`（幂等）+ `init-scripts/01-schema.sql` 同步。
- AI 画线读写仅经服务层与 Agent 工具，不暴露创建端点。

## 6. 后端服务与 API

```
services/market/kline_drawing_service.py
├── 用户画线 CRUD（create/update/delete，均校验 user 归属）
└── AI 画线集读写（replace / append / 单条改 / 单条删 / 清空，均按 user_id 隔离）

api/v1/drawings.py（薄路由，登录态）
├── GET    /kline-drawings?target_type=&target_code=        # 全周期 user + ai（均为当前用户）
├── POST   /kline-drawings                                   # 用户画线创建（批量容忍）
├── PATCH  /kline-drawings/{id}                              # 形态/样式/文字更新
├── DELETE /kline-drawings/{id}
├── POST   /kline-drawings/ai/adopt                          # AI 单条采纳 → 复制为用户画线
├── PATCH  /kline-drawings/ai/item                           # AI 画线单条原位编辑（F-DRAW-08）
├── DELETE /kline-drawings/ai/item                           # AI 画线单条删除
└── DELETE /kline-drawings/ai/clear                          # AI 画线集清空
```

- 性能：单标的画线量为几十行，命中 `(user_id, …)` 前缀索引，GET ≤100ms；不做请求路径聚合计算。
- 校验：锚点 `date` 必须可解析、`price` 有限值；对不存在的 bar 日期按 4.1 对齐规则吸附最近 bar（LLM 输出的宽容归一在服务层完成）。

## 7. Agent 双向接线

### 7.1 读（画线 → 上下文）

- **查询工具（读协议唯一载体）**：`get_kline_drawings(target_type, target_code)` 按**当前会话属主**返回全周期结构化 JSON（用户画线 + 本人的 AI 画线组），登记进 `build_assistant_tools()`；SKILL 指引明确「分析标的趋势/技术形态前先取画线」。
- **共享复盘不注入用户画线**：`stock_daily_analysis` / `market_daily_review` 产物是全局共享缓存（按标的+日期一份），注入任何用户的私有画线都会经缓存泄漏给其他用户——多租户口径下画线上下文只经 per-user 的助手工具路径进入分析。
- **解读指引**：相关 SKILL.md / prompt.yaml 增补——画线文字标注代表用户观点，采纳直接引用，分歧须显式说明依据。

### 7.2 写（对话 → AI 画线）

```
用户对话/页面按钮
  → kline-smart-drawing skill（取数分析）
  → get_kline_drawings 检查已有画线
  →（已有 → ask_user 问题卡：变更 replace / 保留并新增 append / 删除后重画 / 取消）
  → persist_ai_kline_drawings(mode, drawings[])        # 工具层调服务层
  → page_event("kline_drawing.complete", ...)          # __event__ 标记
  → SSE custom 事件 → pageEvents.ts 注册表 → 图表页订阅刷新 AI 图层
```

- prompt/工具与前端共用同一画线 JSON 契约；结构化输出字段不带默认值（无画线返回 `[]`）。

### 7.3 ask_user 问题卡（通用底座）

- `ask_user(question, options[{value,label}], default?)` 为 assistant 工具：以结构化问题**结束本轮**，runtime 检测标记后经 SSE 下发 `question` 自定义事件，不引入长连接暂停。
- 侧边栏（`stores/assistant.ts` 扩展 questionCard 状态）渲染选项按钮；点击后选项文本作为用户消息 `sendQuestion` 续跑线程，Agent 凭上下文继续执行。
- 该机制先服务于画线前确认，后续任何需要用户决策的交互式 skill 复用。

## 8. 权限与边界

- 用户画线端点登录即可，查改删强校验 `user_id` 归属；AI 画线同样 per-user 隔离（读写均限本人），写仅经 Agent 工具/服务层。
- 分钟线不提供画线；画线层异常（渲染/换算）静默降级 + 控制台告警，不影响主图。
- 移动端画线（只读展示）、斐波那契等扩展类型、AI 画线历史版本：见需求文档 §7 功能边界，架构留位不预建。

## 9. 后续文档索引

- [04-ai-agent.md](./04-ai-agent.md) — Skill 体系、`build_assistant_tools` 与 SSE 事件链
- [05-web-frontend.md](./05-web-frontend.md) — 前端架构、图表组件与状态管理
- [03-data-storage.md](./03-data-storage.md) — 表命名约定与迁移规范
