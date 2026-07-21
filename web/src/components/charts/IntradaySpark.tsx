import { useColorScheme } from '@/stores/settings'
import { changeHex } from '@/utils/formatters'

interface IntradaySparkProps {
  points?: number[]
  changePct: number | null
  width?: number
  height?: number
}

/** 全天分时缩略图（纯 SVG，收盘价折线 + 淡色面积，按当日涨跌着色）。 */
export function IntradaySpark({
  points,
  changePct,
  width = 88,
  height = 24,
}: IntradaySparkProps) {
  useColorScheme()

  if (!points || points.length < 2) {
    return (
      <span
        className="inline-block text-center text-xs text-gray-600"
        style={{ width }}
      >
        -
      </span>
    )
  }

  const pad = 1
  const min = Math.min(...points)
  const max = Math.max(...points)
  const span = max - min || 1
  const coords = points.map((value, index) => {
    const x = pad + (index / (points.length - 1)) * (width - pad * 2)
    const y = pad + (1 - (value - min) / span) * (height - pad * 2)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  const color = changeHex(changePct)
  const area = `${pad},${height - pad} ${coords.join(' ')} ${width - pad},${height - pad}`

  return (
    <svg width={width} height={height} className="inline-block shrink-0">
      <polygon points={area} fill={color} opacity={0.12} />
      <polyline
        points={coords.join(' ')}
        fill="none"
        stroke={color}
        strokeWidth={1.2}
      />
    </svg>
  )
}
