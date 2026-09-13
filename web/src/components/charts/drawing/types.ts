/**
 * 画线图层类型（前端单一真相源：shared/types/drawing.ts re-export + 前端专属渲染态）。
 * 架构：docs/arch/09-kline-drawing.md §3
 */

import type { KlineDrawingDirection, KlineDrawingType } from '@ai-invest/shared'

export type {
  AiKlineDrawingGroup,
  AiKlineDrawingItem,
  KlineDrawingAnchor,
  KlineDrawingDirection,
  KlineDrawingLineStyle,
  KlineDrawingPeriod,
  KlineDrawingStyle,
  KlineDrawingTargetType,
  KlineDrawingType,
  UserKlineDrawing,
  UserKlineDrawingCreateRequest,
  UserKlineDrawingUpdateRequest,
} from '@ai-invest/shared'

/** 图层元素统一 id 前缀（graphic 元素命名空间，避免与主图 graphic 冲突） */
export const DRAWING_ROOT_PREFIX = 'kline-drawing-root'
export const AI_LAYER_COLOR = '#7b85ff'
export const AI_LAYER_DASH = [7, 5]

/** 画线类型中文名（工具条/清单共用） */
export const DRAWING_TYPE_LABEL: Record<KlineDrawingType, string> = {
  trendline: '趋势线',
  ray: '射线',
  hline: '水平线',
  box: '箱体',
  text: '文字',
}

/** 绘制操作提示（工具条 tooltip 与绘制中状态 chip 共用） */
export const DRAWING_TOOL_HINTS: Record<KlineDrawingType, string> = {
  trendline: '点击起点与终点（或按住拖拽）绘制线段',
  ray: '点击起点与终点（或按住拖拽）绘制射线',
  hline: '在图上点击一点放置水平线',
  box: '点击对角两点（或按住拖拽）绘制箱体',
  text: '点击图上位置放置文字标注',
}

/** 射线方向中文名 */
export const DIRECTION_LABEL: Record<KlineDrawingDirection, string> = {
  left: '向左',
  right: '向右',
  both: '双向',
}
