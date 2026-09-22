import type { Dayjs } from 'dayjs'
import dayjs from 'dayjs'

import type { ApiCollectorHealthTaskItem, CollectorErrorCause, CollectorHealthStatus } from '@ai-invest/shared'

/** 状态 → 展示元数据（色板与原型 collector-monitoring.html 一致；bg 为同色软底，双主题可读）。 */
export const STATUS_META: Record<
  CollectorHealthStatus,
  { label: string; color: string; bg: string }
> = {
  healthy: { label: '健康', color: '#2ea043', bg: 'rgba(46, 160, 67, 0.12)' },
  degraded: { label: '降级', color: '#d29922', bg: 'rgba(210, 153, 34, 0.14)' },
  critical: { label: '故障', color: '#f85149', bg: 'rgba(248, 81, 73, 0.12)' },
  silent: { label: '静默', color: '#f85149', bg: 'rgba(248, 81, 73, 0.12)' },
  paused: { label: '已暂停', color: '#8a8f98', bg: 'rgba(128, 128, 128, 0.12)' },
  unconfigured: { label: '未配置', color: '#8a8f98', bg: 'rgba(128, 128, 128, 0.12)' },
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

/** 明细表内联的小号角色徽标（原型 role-tag 风格：主=蓝 / 备=灰 / 单=紫）。 */
export const ROLE_CHIP: Record<string, { label: string; color: string; bg: string }> = {
  primary: { label: '主', color: '#58a6ff', bg: 'rgba(88, 166, 255, 0.14)' },
  backup: { label: '备', color: '#8a8f98', bg: 'rgba(128, 128, 128, 0.14)' },
  single: { label: '单', color: '#8b93e8', bg: 'rgba(94, 106, 210, 0.14)' },
}

export const DOMAIN_META: Record<string, { label: string }> = {
  kline: { label: 'K线' },
  quote: { label: '行情' },
  pool: { label: '股池' },
  'fund-flow': { label: '资金流' },
  news: { label: '资讯' },
  fundamental: { label: '基本面' },
  ai: { label: 'AI' },
  kb: { label: '知识库' },
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

/** 最近成功的 humanize 文案（原型「距最近成功」列：今天 HH:mm / 昨天 HH:mm / N 天前 / 超一个月回退日期）。 */
export function lastSuccessText(iso: string | null, now: Dayjs = dayjs()): string {
  if (!iso) return '从未成功'
  const t = dayjs(iso)
  if (t.isSame(now, 'day')) return `今天 ${t.format('HH:mm')}`
  if (t.isSame(now.subtract(1, 'day'), 'day')) return `昨天 ${t.format('HH:mm')}`
  const days = now.diff(t.startOf('day'), 'day')
  if (days < 30) return `${days} 天前`
  return t.format('MM-DD')
}

export interface DomainGroupStat {
  domain: string
  total: number
  abnormal: number
}

/** 按数据域统计实例数与异常数（明细表域头行用；保持首次出现顺序）。 */
export function domainGroupStats(tasks: ApiCollectorHealthTaskItem[]): DomainGroupStat[] {
  const acc = new Map<string, DomainGroupStat>()
  for (const task of tasks) {
    const group = acc.get(task.domain) ?? { domain: task.domain, total: 0, abnormal: 0 }
    group.total += 1
    if (task.status === 'critical' || task.status === 'silent' || task.status === 'degraded') {
      group.abnormal += 1
    }
    acc.set(task.domain, group)
  }
  return [...acc.values()]
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
