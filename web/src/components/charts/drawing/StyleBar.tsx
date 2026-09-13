/**
 * 选中画线的浮动样式条：6 色 / 线型 / 线宽 / 文字 / 删除。
 * 定位由集成层依据选中画线首锚点像素位置计算（getSelectedPixelPos）。
 */

import { DeleteOutlined } from '@ant-design/icons'
import { Input, Popconfirm, Tooltip } from 'antd'

import { DRAWING_COLORS } from '@/stores/drawing'
import type { KlineDrawingLineStyle, UserKlineDrawing } from './types'

const LINE_STYLES: { value: KlineDrawingLineStyle; label: string }[] = [
  { value: 'solid', label: '实线' },
  { value: 'dashed', label: '虚线' },
  { value: 'dotted', label: '点线' },
]

const WIDTHS: (1 | 2 | 3)[] = [1, 2, 3]

export interface StyleBarProps {
  drawing: UserKlineDrawing
  position: { left: number; top: number }
  onPatch: (patch: {
    style?: UserKlineDrawing['style']
    text?: string | null
    direction?: UserKlineDrawing['direction']
  }) => void
  onDelete: () => void
}

export function StyleBar({ drawing, position, onPatch, onDelete }: StyleBarProps) {
  const chip = (active: boolean, color?: string): React.CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: 18,
    height: 18,
    padding: '0 4px',
    fontSize: 10,
    borderRadius: 3,
    border: `1px solid ${active ? '#5e6ad2' : 'rgba(255,255,255,0.12)'}`,
    background: active ? 'rgba(94,106,210,0.18)' : 'transparent',
    color: color ?? (active ? '#aeb4ff' : '#8c8c8c'),
    cursor: 'pointer',
  })

  return (
    <div
      className="absolute z-20 flex items-center gap-1.5 rounded-md border px-2 py-1"
      style={{
        left: position.left,
        top: position.top,
        borderColor: 'rgba(255,255,255,0.1)',
        background: '#1a1d24',
        boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
      }}
      onMouseDown={(e) => e.stopPropagation()}
    >
      {DRAWING_COLORS.map((c) => (
        <button
          key={c}
          type="button"
          title={c}
          style={{
            ...chip(drawing.style.color === c),
            width: 18,
            padding: 0,
            background: drawing.style.color === c ? 'transparent' : c,
          }}
          onClick={() => onPatch({ style: { ...drawing.style, color: c } })}
        >
          {drawing.style.color === c ? <span className="block h-2.5 w-2.5 rounded-sm" style={{ background: c }} /> : null}
        </button>
      ))}
      <span className="h-4 w-px bg-white/10" />
      {LINE_STYLES.map((ls) => (
        <button
          key={ls.value}
          type="button"
          style={chip(drawing.style.lineStyle === ls.value)}
          onClick={() => onPatch({ style: { ...drawing.style, lineStyle: ls.value } })}
        >
          {ls.label}
        </button>
      ))}
      <span className="h-4 w-px bg-white/10" />
      {WIDTHS.map((w) => (
        <button
          key={w}
          type="button"
          style={chip(drawing.style.width === w)}
          onClick={() => onPatch({ style: { ...drawing.style, width: w } })}
        >
          {w}px
        </button>
      ))}
      {drawing.drawingType === 'ray' && (
        <>
          <span className="h-4 w-px bg-white/10" />
          {(['right', 'both', 'left'] as const).map((dir) => (
            <button
              key={dir}
              type="button"
              style={chip(drawing.direction === dir)}
              onClick={() => onPatch({ direction: dir })}
            >
              {dir === 'right' ? '向右' : dir === 'both' ? '双向' : '向左'}
            </button>
          ))}
        </>
      )}
      <span className="h-4 w-px bg-white/10" />
      <Input
        size="small"
        variant="filled"
        placeholder="标注文字"
        defaultValue={drawing.text ?? ''}
        style={{ width: 110, fontSize: 11 }}
        onPressEnter={(e) => onPatch({ text: (e.target as HTMLInputElement).value || null })}
        onBlur={(e) => {
          const v = e.target.value
          if (v !== (drawing.text ?? '')) onPatch({ text: v || null })
        }}
      />
      <Popconfirm title="删除该画线？" okText="删除" cancelText="取消" onConfirm={onDelete}>
        <Tooltip title="删除（Del）">
          <button type="button" style={{ ...chip(false), color: '#e35d6a' }}>
            <DeleteOutlined />
          </button>
        </Tooltip>
      </Popconfirm>
    </div>
  )
}
