export function formatNumber(value: number, decimals = 2): string {
  return value.toFixed(decimals)
}

export function formatPercent(value: number, decimals = 2): string {
  return `${value > 0 ? '+' : ''}${value.toFixed(decimals)}%`
}
