/**
 * K 线族图表共享常量与格式化（IndexKlineChart / stockChartView klineOption 等共用）。
 * 仅放逐字重复的纯常量/纯函数，不含 ECharts 实例逻辑。
 */

export const FONT_MONO = "'SF Mono','Fira Code','Consolas',monospace"
export const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

export function fmt(v: number | null | undefined, decimals = 2): string {
  return v == null ? '--' : v.toFixed(decimals)
}

export function signed(v: number | null | undefined, decimals = 2): string {
  if (v == null) return '--'
  return `${v > 0 ? '+' : ''}${v.toFixed(decimals)}`
}

/** 最新价胶囊（markLine 右轴端点标签）配置，color 为胶囊底色（涨跌色） */
export function lastPriceLabel(close: number | null | undefined, color: string) {
  return {
    show: true,
    position: 'end' as const,
    formatter: fmt(close),
    backgroundColor: color,
    color: '#fff',
    borderRadius: 3,
    padding: [1, 5],
    fontSize: 10,
    fontFamily: FONT_MONO,
    distance: 2,
  }
}
