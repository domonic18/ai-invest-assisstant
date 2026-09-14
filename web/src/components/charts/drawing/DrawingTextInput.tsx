/**
 * 文字标注输入框（同花顺式）：文字工具点击落点弹出，Enter 提交、Esc/失焦取消。
 * 由 DrawingLayerHost 在编辑态渲染于图表容器内，定位坐标与图表容器一致。
 */

import { useEffect, useRef } from 'react'
import { Input } from 'antd'
import type { InputRef } from 'antd'

interface DrawingTextInputProps {
  position: { left: number; top: number }
  /** 图表容器尺寸（落点靠右/靠下时输入框越界回收） */
  bounds: { width: number; height: number }
  /** 编辑已有文字标注时的初始文案 */
  initial?: string
  onSubmit: (value: string) => void
  onCancel: () => void
}

export function DrawingTextInput({ position, bounds, initial, onSubmit, onCancel }: DrawingTextInputProps) {
  const ref = useRef<InputRef>(null)

  useEffect(() => {
    ref.current?.focus()
    if (initial) ref.current?.select()
    // 仅挂载时聚焦一次
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div
      className="absolute z-30 rounded-md border px-2 py-1.5"
      style={{
        // 输入框约 200×38：靠右/靠下越界时向内回收
        left: Math.min(Math.max(4, position.left + 10), Math.max(4, bounds.width - 204)),
        top: Math.min(Math.max(4, position.top - 14), Math.max(4, bounds.height - 42)),
        borderColor: 'rgba(94,106,210,0.55)',
        background: '#1a1d24',
        boxShadow: '0 4px 12px rgba(0,0,0,0.45)',
      }}
      onMouseDown={(e) => e.stopPropagation()}
    >
      <Input
        ref={ref}
        size="small"
        variant="filled"
        placeholder="输入标注文字，Enter 确认"
        defaultValue={initial}
        maxLength={60}
        style={{ width: 180, fontSize: 12 }}
        onPressEnter={(e) => onSubmit((e.target as HTMLInputElement).value)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            e.stopPropagation()
            onCancel()
          }
        }}
        onBlur={onCancel}
      />
    </div>
  )
}
