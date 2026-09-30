/**
 * 资源站心跳文案推导（纯函数，可测）：从 Celery 任务方框 + 系统状态探测
 * 推导知识库 / 资讯 / 情绪 / 柜台 / 总线的「文字+灯」双通道心跳，
 * 状态不依赖颜色。匹配不到实时数据时如实显示「今日静默」，不虚报在线。
 */
import dayjs from 'dayjs'

import type { CeleryTaskSquare, ServiceStatusItem } from '@ai-invest/shared'

import { toBeijing } from '@/utils/beijing'

/** 提取北京墙钟 HH:MM（资源站心跳是业务时间线语义，禁止环境本地时区）。 */
function hm(iso: string): string {
  return toBeijing(dayjs(iso)).format('HH:mm')
}

function matches(task: CeleryTaskSquare, keywords: string[]): boolean {
  const haystack = `${task.taskType} ${task.label} ${task.source ?? ''} ${task.detail ?? ''}`.toLowerCase()
  return keywords.some((kw) => haystack.includes(kw))
}

/**
 * 领域心跳：running 优先，其次今日最近一次成功时刻，否则今日静默。
 * @param tasks 全部队列任务方框（已 flatten）
 * @param keywords 领域关键词（taskType/label/source/detail 子串）
 * @param today 基准日 YYYY-MM-DD（传 bjNow() 的格式串，便于测试固定）
 */
export function domainHeartbeat(tasks: CeleryTaskSquare[], keywords: string[], today: string): string {
  const pool = tasks.filter((t) => matches(t, keywords))
  const running = pool.find((t) => t.state === 'running')
  if (running) return `执行中 · ${running.label}`
  const succeeded = pool
    .filter((t) => (t.state === 'success' || t.state === 'partial') && t.finishedAt)
    .sort((a, b) => dayjs(b.finishedAt!).valueOf() - dayjs(a.finishedAt!).valueOf())
  const latest = succeeded[0]
  if (latest && toBeijing(dayjs(latest.finishedAt)).format('YYYY-MM-DD') === today) {
    return `最近成功 ${hm(latest.finishedAt!)}`
  }
  return '今日静默'
}

/** 柜台心跳：up/down + 探测延迟；无数据时「状态未知」。 */
export function counterHeartbeat(item: ServiceStatusItem | null | undefined): {
  up: boolean | null
  text: string
} {
  if (!item) return { up: null, text: '状态未知' }
  if (item.status !== 'up') return { up: false, text: `离线${item.error ? ` · ${item.error}` : ''}` }
  return { up: true, text: item.latencyMs != null ? `HB ${item.latencyMs}ms` : '在线' }
}
