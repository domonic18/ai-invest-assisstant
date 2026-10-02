/**
 * 板面五态小注（丝印级）：一行式芯片五态速读，置于主板左上空区（TP1 右侧）。
 * 替代原型板下三张解读卡——那是示例说明，正式页只在板上留最小注记。
 */
import { BOARD, MONO } from './boardTheme'

const ITEMS: ReadonlyArray<{ color: string; opacity?: number; label: string }> = [
  { color: BOARD.cyan, label: '工作·满载跑马' },
  { color: BOARD.purple, label: '已产出·回落' },
  { color: BOARD.purple, opacity: 0.5, label: '待机·慢心跳' },
  { color: BOARD.amberPaused, label: '暂停·门控' },
  { color: BOARD.socketGrey, label: '未启用·空槽' },
]

export function StateLegend({ x = 124, y = 52 }: { x?: number; y?: number }) {
  // 首个图例项须让出「芯片五态」标签宽度（4 字 ≈38px），否则色点压在标签文字上
  let cx = x + 56
  return (
    <g>
      <rect x={x} y={y} width="486" height="28" rx="6" fill="#0e1512" stroke="rgba(148,163,184,.16)" />
      <text x={x + 12} y={y + 18.5} fontSize="8.5" fill={BOARD.grey} letterSpacing="1" style={{ fontFamily: MONO }}>
        芯片五态
      </text>
      {ITEMS.map((item) => {
        const dotX = cx + 4
        const textX = cx + 11
        cx = textX + item.label.length * 9.2 + 16
        return (
          <g key={item.label}>
            <circle cx={dotX} cy={y + 15.5} r="3" fill={item.color} fillOpacity={item.opacity ?? 0.9} />
            <text x={textX} y={y + 18.5} fontSize="9" fill={BOARD.textMid}>
              {item.label}
            </text>
          </g>
        )
      })}
    </g>
  )
}
