/**
 * 画线编辑态触发按钮（同花顺式）：点击进入/退出编辑态，
 * 编辑态时图表左缘出现 DrawingSideBar 竖排工具栏。状态在 useDrawingStore。
 */

import { EditOutlined } from '@ant-design/icons'

import { useDrawingStore } from '@/stores/drawing'

export function DrawingToolbar({ className }: { className?: string }) {
  const toolbarOpen = useDrawingStore((s) => s.toolbarOpen)
  const enterDrawing = useDrawingStore((s) => s.enterDrawing)
  const exitDrawing = useDrawingStore((s) => s.exitDrawing)

  const style: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    padding: '2px 8px',
    fontSize: 11,
    lineHeight: '18px',
    borderRadius: 4,
    border: `1px solid ${toolbarOpen ? '#5e6ad2' : '#23262d'}`,
    color: toolbarOpen ? '#aeb4ff' : '#8a8f98',
    background: toolbarOpen ? 'rgba(94,106,210,0.14)' : 'transparent',
    cursor: 'pointer',
  }

  return (
    <button
      type="button"
      className={`inline-flex items-center ${className ?? ''}`}
      style={style}
      title={toolbarOpen ? '退出画线' : '画线工具'}
      onClick={() => (toolbarOpen ? exitDrawing() : enterDrawing())}
    >
      <EditOutlined style={{ fontSize: 11 }} />
      画线
    </button>
  )
}
