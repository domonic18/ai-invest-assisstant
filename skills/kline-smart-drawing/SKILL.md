---
name: kline-smart-drawing
description: K 线 AI 智能画线：分析当前标的的价格结构，把关键压力/支撑位、趋势边界与箱体整理区间以 AI 画线落到图表上（虚线 + AI 徽标，可原位编辑与采纳）。仅侧边栏对话触发，定时任务不画线。
allowed-tools: get_kline_drawings, get_stock_kline, get_index_technical, get_stock_quote, search_knowledge_base, ask_user, persist_ai_kline_drawings
---

# K 线 AI 智能画线

## 描述
在用户当前查看的标的（个股 / 指数 / 板块，取自页面上下文或用户指定）K 线图上生成 AI 画线：以真实 K 线数据识别关键压力位、支撑位、趋势线边界与箱体整理区间，写入 AI 画线集后在图表 AI 图层渲染（虚线锁定样式 + AI 徽标 + hover 出 label/reason）。AI 画线是可变工作区，用户可原位编辑、单条采纳为用户画线、整组清除后重新生成。

## 触发条件
- 仅侧边栏对话路径：用户要求"画出/标注压力位支撑位、趋势线、箱体、关键价位"等画线动作，或点击页面「AI 画线」预置按钮
- 页面上下文给出标的（stock_code / index_code / sector_type + sector_code）时直接使用；用户口头指定标的时以用户为准
- **定时/复盘类任务一律不调用**（复盘只读画线，见 market-daily-review / stock-daily-analysis 的用户画线解读节）

## 分析流程
1. **确定标的与周期**：默认日线；用户要求周线/月线时切换
2. **检查已有画线**：调 `get_kline_drawings(target_type, target_code)`
   - 存在**用户画线**（user 组非空）→ 必须 `ask_user` 确认处理策略，选项：
     - `append` 保留并新增（默认推荐）：AI 画线叠加，不碰用户画线
     - `replace` 覆盖 AI 画线：仅重画 AI 组，同样不碰用户画线
     - `cancel` 取消画线
   - 不给出"删除用户画线"选项；用户主动要求删除时，指引其到画线清单手动删除
   - 仅存在 AI 画线（user 组为空）→ 默认 `replace` 重画，无需确认
3. **取数分析**：调 `get_stock_kline`（个股，limit 覆盖用户所述区间，近半年≈120）/ `get_index_technical`（指数预计算指标）等取真实 K 线；识别：
   - 压力/支撑：至少两次触碰且未突破（射线 `ray`，锚点放两次触碰的 bar）
   - 趋势边界：连接同向 swing 高/低点（`trendline`）
   - 箱体整理：区间上下沿（`box`，锚点为区间两角）
   - 精确价位：`hline`（锚点仅 price）
   - 形态定性存疑时调 `search_knowledge_base(query=<形态/趋势相关关键词>)` 检索课程方法论佐证（`include_media` 保持 false）；引用卡片时保留 citation 定位
4. **写入**：调 `persist_ai_kline_drawings(target_type, target_code, period, drawings, mode, sector_type?)`
   - 锚点 `date` 必须取自工具返回的真实 K 线日期——校验失败会返回错误，按错误提示修正后重试
   - `label` 组内唯一且语义化（如"近半年压力位"）；`reason` 一句话给出依据（触碰次数/量能特征）
   - 条数克制：一图 3-8 条为宜，宁缺毋滥
5. **收尾**：告知已画 N 条及各自含义（一两句话逐条），提示可在图上直接拖拽微调、双击改名、清单里单条采纳

## 输出 Schema
`persist_ai_kline_drawings` 的 drawings 数组每项：

```json
{
  "drawing_type": "trendline | ray | hline | box | text",
  "anchors": [{"date": "YYYY-MM-DD", "price": 21.4}],
  "direction": "right",
  "label": "近半年压力位",
  "reason": "240227 与 250512 两测 21.4 放量回落"
}
```

## 边界与纪律
- **锚点即契约**：date/price 必须来自工具取数，禁止估算或编造日期
- 用户画线是用户资产：任何 mode 都不会删改用户画线；分析叙述中须尊重用户画线语义（分歧显式说明）
- 无画线需求（用户只是问趋势）时不要主动画线；画线动作以用户明确请求为限
