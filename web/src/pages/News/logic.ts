/** 资讯中心纯展示逻辑：AI 分级三档、跨日分组、新讯息计数。 */
import dayjs, { type Dayjs } from 'dayjs'

import type { TelegraphItem } from '@ai-invest/shared'

export type ScoreBand = 'high' | 'mid' | 'low' | 'unscored'

/** 三档阈值与后端评分口径一致：≥70 高 / 40-69 中 / <40 低；null 未分级。 */
export const SCORE_HIGH_MIN = 70
export const SCORE_MID_MIN = 40

export function scoreBand(aiScore: number | null): ScoreBand {
  if (aiScore === null) return 'unscored'
  if (aiScore >= SCORE_HIGH_MIN) return 'high'
  if (aiScore >= SCORE_MID_MIN) return 'mid'
  return 'low'
}

export interface NewsDayGroup {
  /** 分组键（本地时区 YYYY-MM-DD）。 */
  day: string
  /** 分隔条文案：今天 / 昨天 / M月D日。 */
  label: string
  items: TelegraphItem[]
}

/** 按发布日期（本地时区）把降序列表切成连续同日分组。 */
export function groupByDay(
  items: TelegraphItem[],
  now: Dayjs = dayjs(),
): NewsDayGroup[] {
  const groups: NewsDayGroup[] = []
  for (const item of items) {
    const day = dayjs(item.publishTime).format('YYYY-MM-DD')
    const last = groups[groups.length - 1]
    if (last && last.day === day) {
      last.items.push(item)
    } else {
      groups.push({ day, label: dayLabel(day, now), items: [item] })
    }
  }
  return groups
}

function dayLabel(day: string, now: Dayjs): string {
  const diffDays = now.startOf('day').diff(dayjs(day).startOf('day'), 'day')
  if (diffDays === 0) return '今天'
  if (diffDays === 1) return '昨天'
  return dayjs(day).format('M月D日')
}

/** 高于已确认首条 id 的条目数（cls_msg_id 单调递增）；0 表示无新讯息。 */
export function countNewMessages(
  items: TelegraphItem[],
  seenTopId: number | null,
): number {
  if (seenTopId === null || items.length === 0) return 0
  return items.filter((item) => item.clsMsgId > seenTopId).length
}

/** 资讯流已接入数据的渠道（渠道注册表见后端 news_channel_service；迭代 4 多源聚合后扩展）。 */
const WIRED_FEED_CHANNELS = new Set(['cls_telegraph'])

/** 渠道 chip 是否可筛选：未接入数据的渠道置灰不可点，避免「选中无效果」的误导。 */
export function isChannelWired(key: string): boolean {
  return WIRED_FEED_CHANNELS.has(key)
}

const NOISE_CATEGORY_RE = /^-?\d+$/

/** cls 原始 category 为数字编码（-1 = 无分类哨兵），对用户无意义不展示。 */
export function isNoiseCategory(category: string | null): boolean {
  return category === null || NOISE_CATEGORY_RE.test(category)
}

/** cls importance：1 = C 级（一般，占绝对多数）不展示降噪；仅 关注(2)/重要(3) 出 Tag。 */
export function isNoiseImportance(importance: number | null): boolean {
  return importance === null || importance < 2
}
