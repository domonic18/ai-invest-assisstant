/**
 * K 线画线 wire 契约（F-DRAW）。
 * 锚点一律为数据坐标 (date, price)——画线可被 Agent 结构化读写的前提，
 * 像素坐标只在渲染瞬间存在，禁止落库。
 * 架构：docs/arch/09-kline-drawing.md §4；需求：docs/requirement/03-kline-drawing-requirement.md §4/§5.9
 */

export type KlineDrawingTargetType = 'stock' | 'index' | 'sector'
export type KlineDrawingPeriod = 'daily' | 'weekly' | 'monthly'
export type KlineDrawingType = 'trendline' | 'ray' | 'hline' | 'box' | 'text'
export type KlineDrawingDirection = 'left' | 'right' | 'both'
export type KlineDrawingLineStyle = 'solid' | 'dashed' | 'dotted'

export interface KlineDrawingAnchor {
  /** 北京交易日历日 YYYY-MM-DD；hline 不需要 x 锚点，存空串 */
  date: string
  price: number
}

export interface KlineDrawingStyle {
  color: string
  lineStyle: KlineDrawingLineStyle
  width: 1 | 2 | 3
}

/** 用户画线（per-user 私有，归属键 user_id + target + period） */
export interface UserKlineDrawing {
  id: string
  targetType: KlineDrawingTargetType
  targetCode: string
  period: KlineDrawingPeriod
  drawingType: KlineDrawingType
  anchors: KlineDrawingAnchor[]
  direction?: KlineDrawingDirection
  /** 画线携带的标注文案（box/text 必有，其余可选）——Agent 读的一等信号 */
  text?: string
  style: KlineDrawingStyle
}

export interface UserKlineDrawingCreateRequest {
  targetType: KlineDrawingTargetType
  targetCode: string
  period: KlineDrawingPeriod
  drawingType: KlineDrawingType
  anchors: KlineDrawingAnchor[]
  direction?: KlineDrawingDirection
  text?: string
  style: KlineDrawingStyle
}

/** 用户画线部分更新：仅提交变更字段 */
export interface UserKlineDrawingUpdateRequest {
  anchors?: KlineDrawingAnchor[]
  direction?: KlineDrawingDirection
  text?: string | null
  style?: KlineDrawingStyle
}

/** AI 画线单项（Agent 产出，label 组内唯一） */
export interface AiKlineDrawingItem {
  drawingType: KlineDrawingType
  anchors: KlineDrawingAnchor[]
  direction?: KlineDrawingDirection
  label: string
  /** 归因说明（如「两高点连线，两次受阻回落」），hover tooltip 展示 */
  reason: string
}

/** AI 画线集（全局共享、可变工作区，每标的每周期一套） */
export interface AiKlineDrawingGroup {
  targetType: KlineDrawingTargetType
  targetCode: string
  period: KlineDrawingPeriod
  skillId: string
  /** 最近一次生成对应交易日 YYYY-MM-DD（展示用） */
  tradeDate: string | null
  summary?: string
  drawings: AiKlineDrawingItem[]
}

/** GET /kline-drawings 响应：该标的全部周期的 user + ai 两组 */
export interface KlineDrawingsResponse {
  user: UserKlineDrawing[]
  ai: AiKlineDrawingGroup[]
}
