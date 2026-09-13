import type { CollectorErrorCause, CollectorHealthStatus } from '@ai-invest/shared'

/** 状态 → 展示元数据（色板与原型 collector-monitoring.html 一致）。 */
export const STATUS_META: Record<CollectorHealthStatus, { label: string; color: string }> = {
  healthy: { label: '健康', color: '#2ea043' },
  degraded: { label: '降级', color: '#d29922' },
  critical: { label: '故障', color: '#f85149' },
  silent: { label: '静默', color: '#f85149' },
  paused: { label: '已暂停', color: '#8a8f98' },
  unconfigured: { label: '未配置', color: '#8a8f98' },
}

export const STATUS_ORDER: CollectorHealthStatus[] = [
  'critical',
  'silent',
  'degraded',
  'healthy',
  'paused',
  'unconfigured',
]

export const ROLE_META: Record<string, { label: string; color: string }> = {
  primary: { label: '主渠道', color: 'blue' },
  backup: { label: '备渠道', color: 'default' },
  single: { label: '单渠道', color: 'purple' },
}

export const DOMAIN_META: Record<string, { label: string }> = {
  kline: { label: 'K线' },
  quote: { label: '行情' },
  pool: { label: '股池' },
  'fund-flow': { label: '资金流' },
  news: { label: '资讯' },
  fundamental: { label: '基本面' },
  ai: { label: 'AI' },
}

export const DOMAIN_OPTIONS = Object.entries(DOMAIN_META).map(([value, meta]) => ({
  value,
  label: meta.label,
}))

export function domainLabel(domain: string): string {
  return DOMAIN_META[domain]?.label ?? domain
}

export function causeLabel(cause: string | null): string | null {
  if (!cause) return null
  return CAUSE_LABELS[cause as CollectorErrorCause] ?? cause
}

/** 成功率（0-1 小数）→ 百分比文案；null → '-'。 */
export function rateText(value: number | null, decimals = 1): string {
  if (value == null) return '-'
  return `${(value * 100).toFixed(decimals)}%`
}

const CAUSE_LABELS: Record<CollectorErrorCause, string> = {
  waf: 'WAF/反爬',
  network: '网络/超时',
  parse: '接口/解析',
  auth: '认证/配额',
  timeout: '任务超时',
  not_ready: '输入未就绪',
  other: '其他',
}

export const CAUSE_OPTIONS = (Object.entries(CAUSE_LABELS) as [CollectorErrorCause, string][]).map(
  ([value, label]) => ({ value, label }),
)
