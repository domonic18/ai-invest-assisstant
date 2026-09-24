/**
 * 画线图层类型（前端单一真相源：shared/types/drawing.ts re-export + 前端专属渲染态）。
 * 架构：docs/arch/09-kline-drawing.md §3
 */

import type { ECharts } from 'echarts'
import type {
  AiKlineDrawingItem,
  KlineDrawingAnchor,
  KlineDrawingDirection,
  KlineDrawingType,
  KlineDrawingStyle,
  UserKlineDrawing,
  UserKlineDrawingCreateRequest,
  UserKlineDrawingUpdateRequest,
} from '@ai-invest/shared'

/** 主图 grid 矩形（像素） */
export interface GridRect {
  x: number
  y: number
  width: number
  height: number
}

/** 图表容器内像素点 */
export interface Point {
  x: number
  y: number
}

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

/** AI 画线渲染态稳定 id（集成层按 `${groupKey}:${label}` 生成） */
export type AiDrawingItem = AiKlineDrawingItem & { id: string }

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
  text: '点击图上位置输入文字（Enter 确认），双击已有文字可修改',
}

/** 射线方向中文名 */
export const DIRECTION_LABEL: Record<KlineDrawingDirection, string> = {
  left: '向左',
  right: '向右',
  both: '双向',
}

/** 画线归属域（构造创建请求用） */
export interface DrawingScope {
  targetType: 'stock' | 'index' | 'sector'
  targetCode: string
  period: 'daily' | 'weekly' | 'monthly'
}

/** 文字标注输入请求（新建：anchor 预计算；编辑：drawingId/aiLabel + initial） */
export interface DrawingTextEditRequest {
  /** 图表容器内像素位置（输入框定位） */
  px: Point
  /** 新建时点击处的数据锚点 */
  anchor?: KlineDrawingAnchor
  /** 编辑已有文字标注 */
  drawingId?: string
  /** 编辑 AI 画线 label（双击改名） */
  aiLabel?: string
  initial?: string
}

export interface UseDrawingLayerParams {
  /** echarts-for-react 实例；null 时图层整体静默 */
  chart: ECharts | null
  /** 主图 category x 轴日期序列（与图表 option 同源） */
  dates: string[]
  /** 画线归属域（构造创建请求用） */
  scope: DrawingScope
  /** 当前周期已过滤的用户画线 */
  drawings: UserKlineDrawing[]
  /** 当前周期已过滤的 AI 画线（一期只读渲染，二期原位编辑） */
  aiDrawings: AiDrawingItem[]
  /** 画线工具（null = 未进入画线模式） */
  activeTool: KlineDrawingType | null
  selectedId: string | null
  /** 编辑态（左缘工具栏可见）：仅编辑态下画线可选中/拖动，退出后纯展示（同花顺式） */
  interactive: boolean
  /** 新画线默认样式（记忆值） */
  defaultStyle: KlineDrawingStyle
  onCreate: (req: UserKlineDrawingCreateRequest) => void
  onUpdate: (id: string, patch: UserKlineDrawingUpdateRequest) => void
  onSelect: (id: string | null) => void
  onDelete: (id: string) => void
  /** AI 画线单条原位编辑（编辑态）：拖拽锚点落表 / Delete 删除（双击改名走 onRequestTextInput） */
  onUpdateAiItem: (label: string, patch: { anchors: UserKlineDrawingUpdateRequest['anchors'] }) => void
  onDeleteAiItem: (label: string) => void
  /** Esc 退出画线模式（集成层清空 activeTool） */
  onRequestDisarm: () => void
  /** Esc 最后一级：退出画线编辑态（收起竖排工具栏） */
  onRequestExit?: () => void
  /** 文字工具点击落点 / 双击已有文字标注：请求宿主弹出文字输入框 */
  onRequestTextInput: (req: DrawingTextEditRequest) => void
}
