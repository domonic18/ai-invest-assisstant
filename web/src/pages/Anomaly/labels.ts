/**
 * 异动页展示层文案映射：检测维度 / 归因分类 → 中文标签与徽标配色。
 * 值域与后端 app/services/market/anomaly_common.py 的常量一一对应。
 */

/** 检测维度（anomaly_types 元素，板块/个股共用字面量空间） */
export const ANOMALY_TYPE_LABELS: Record<string, string> = {
  price: '涨跌幅',
  volume: '放量',
  sync: '普涨',
  ma60_breakout: 'MA60 突破',
  turnover: '高换手',
}

/** 板块归因分类 */
export const SECTOR_CATEGORY_LABELS: Record<string, string> = {
  resonance: '趋势共振',
  rotation: '轮动补涨',
}

/** 个股归因分类 */
export const STOCK_CATEGORY_LABELS: Record<string, string> = {
  breakout: '趋势突破',
  acceleration: '趋势内加速',
  pullback: '下跌反抽',
}

/** 归因分类徽标配色（红涨绿跌：多头分类红系、空头绿系） */
export const CATEGORY_COLORS: Record<string, string> = {
  resonance: 'volcano',
  rotation: 'gold',
  breakout: 'red',
  acceleration: 'orange',
  pullback: 'green',
}

export function describeAnomalyTypes(types: string[]): string {
  return types.map((t) => ANOMALY_TYPE_LABELS[t] ?? t).join('、') || '—'
}
