/**
 * 画线编辑态竖排工具栏（同花顺 PC 客户端式）：光标 + 五类型图标 + 删除/清单/关闭。
 * 由 DrawingLayerHost 在编辑态（toolbarOpen）时渲染于图表左缘，普通 DOM 全屏内可见。
 * 状态在 useDrawingStore；删除回调由宿主传入（remove mutation 在宿主层）。
 */

import {
  BorderOutlined,
  CloseOutlined,
  DeleteOutlined,
  FontSizeOutlined,
  MinusOutlined,
  NodeIndexOutlined,
  RiseOutlined,
  SelectOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons'

import type { KlineDrawingType } from './types'
import { DRAWING_TOOL_HINTS, DRAWING_TYPE_LABEL } from './types'
import { useDrawingStore } from '@/stores/drawing'

const TOOLS: { type: KlineDrawingType; icon: React.ReactNode }[] = [
  { type: 'trendline', icon: <NodeIndexOutlined /> },
  { type: 'ray', icon: <RiseOutlined /> },
  { type: 'hline', icon: <MinusOutlined /> },
  { type: 'box', icon: <BorderOutlined /> },
  { type: 'text', icon: <FontSizeOutlined /> },
]

interface DrawingSideBarProps {
  /** 删除当前选中画线（宿主接 remove mutation + 取消选中） */
  onDeleteSelected: () => void
  /** 是否存在选中项（删除按钮可用态） */
  hasSelection: boolean
}

export function DrawingSideBar({ onDeleteSelected, hasSelection }: DrawingSideBarProps) {
  const activeTool = useDrawingStore((s) => s.activeTool)
  const setActiveTool = useDrawingStore((s) => s.setActiveTool)
  const panelOpen = useDrawingStore((s) => s.panelOpen)
  const togglePanel = useDrawingStore((s) => s.togglePanel)
  const exitDrawing = useDrawingStore((s) => s.exitDrawing)

  const btn = (active: boolean): React.CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: 26,
    height: 26,
    fontSize: 13,
    lineHeight: 1,
    borderRadius: 4,
    border: `1px solid ${active ? '#5e6ad2' : 'transparent'}`,
    color: active ? '#aeb4ff' : '#9aa0aa',
    background: active ? 'rgba(94,106,210,0.14)' : 'transparent',
    cursor: 'pointer',
    flexShrink: 0,
  })

  return (
    <div className="absolute left-1.5 top-1.5 z-20 flex max-h-[calc(100%-12px)] flex-col items-center gap-0.5 overflow-y-auto rounded-md border border-white/10 bg-[#1a1d24]/95 p-1 shadow-lg">
      <button
        type="button"
        style={btn(activeTool === null)}
        title={`选择/移动画线（Esc 退出绘制）`}
        onClick={() => setActiveTool(null)}
      >
        <SelectOutlined />
      </button>
      {TOOLS.map((t) => (
        <button
          key={t.type}
          type="button"
          style={btn(activeTool === t.type)}
          title={`${DRAWING_TYPE_LABEL[t.type]}：${DRAWING_TOOL_HINTS[t.type]}`}
          onClick={() => setActiveTool(activeTool === t.type ? null : t.type)}
        >
          {t.icon}
        </button>
      ))}
      <span className="my-0.5 h-px w-5 bg-white/10" />
      <button
        type="button"
        style={btn(false)}
        title="删除选中画线（Delete）"
        disabled={!hasSelection}
        onClick={onDeleteSelected}
        className={hasSelection ? '' : 'cursor-not-allowed opacity-40'}
      >
        <DeleteOutlined />
      </button>
      <button
        type="button"
        style={btn(panelOpen)}
        title="画线清单"
        onClick={togglePanel}
      >
        <UnorderedListOutlined />
      </button>
      <button type="button" style={btn(false)} title="退出画线" onClick={exitDrawing}>
        <CloseOutlined />
      </button>
    </div>
  )
}
