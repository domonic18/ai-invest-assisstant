/**
 * 决策流叙事化映射（纯函数，可测）：逐 tick 观测行 → 「一句人话 + 弱化 mono
 * 附注 + 事件分级」。股票一律「名称+代号」双写（项目界面硬性约定）。
 * 数据口径：盘中逐 tick（含 no_action 心跳行），模板覆盖 execute/suppress/
 * wait/abandon/临近触发/体检告警/尾盘强检/默认心跳。
 */
import dayjs from 'dayjs'

import type { ApiTradingAgentObservationItem } from '@ai-invest/shared'

import { toBeijing } from '@/utils/beijing'

export type NarrativeTone = 'hot' | 'dim' | 'norm'

export interface NarrativeCard {
  key: number
  time: string
  tag: string
  tone: NarrativeTone
  sentence: string
  meta: string
  /** 连续同类条目合并（+N）的分组键之一 */
  stockCode: string
}

function stockLabel(item: ApiTradingAgentObservationItem): string {
  return item.stockName ? `${item.stockName} ${item.stockCode}` : item.stockCode
}

function metaBase(item: ApiTradingAgentObservationItem): string {
  const parts = [`WATCH ${item.stockCode}`, `L0 ${item.l0Verdict}`]
  if (item.changePct != null) parts.push(`${item.changePct}%`)
  return parts.join(' · ')
}

export function toNarrative(item: ApiTradingAgentObservationItem): NarrativeCard {
  const time = toBeijing(dayjs(item.tickTime)).format('HH:mm:ss')
  const stock = stockLabel(item)

  if (item.action === 'execute') {
    const side = item.planType === 'sell' ? '卖单' : '买单'
    const verb = item.planType === 'sell' ? '触发卖点' : '回踩到买区'
    return {
      key: item.id,
      time,
      stockCode: item.stockCode,
      tag: item.planType === 'sell' ? '卖出执行' : '买入执行',
      tone: 'hot',
      sentence: `看着${stock}${verb}，把 ${item.price} 元的${side}递给了柜台`,
      meta: [
        `${item.planType === 'sell' ? 'SELL' : 'BUY'} ${item.stockCode}`,
        item.isShadow ? 'paper' : 'live',
        item.orderVolume != null ? `数量 ${item.orderVolume}` : null,
        item.triggerReason ? `触发 ${item.triggerReason}` : null,
      ]
        .filter(Boolean)
        .join(' · '),
    }
  }
  if (item.action === 'suppress') {
    return {
      key: item.id,
      time,
      stockCode: item.stockCode,
      tag: '抑制',
      tone: 'dim',
      sentence: `想动手，忍住了——${item.suppressionReason ?? item.l0Detail ?? '纪律约束'}`,
      meta: metaBase(item),
    }
  }
  if (item.action === 'wait') {
    return {
      key: item.id,
      time,
      stockCode: item.stockCode,
      tag: '观望',
      tone: 'dim',
      sentence: `再等等——${item.l0Detail ?? '信号未确认'}`,
      meta: metaBase(item),
    }
  }
  if (item.action === 'abandon') {
    return {
      key: item.id,
      time,
      stockCode: item.stockCode,
      tag: '放弃',
      tone: 'dim',
      sentence: `放弃了——${item.l0Detail ?? '条件不满足'}`,
      meta: metaBase(item),
    }
  }
  if (item.decision?.window === 'tail_check') {
    return {
      key: item.id,
      time,
      stockCode: item.stockCode,
      tag: '尾盘强检',
      tone: 'dim',
      sentence: `尾盘强检：${stock} ${item.l0Detail ?? '无动作'}`,
      meta: metaBase(item),
    }
  }
  if (item.l0Verdict === 'near_trigger') {
    return {
      key: item.id,
      time,
      stockCode: item.stockCode,
      tag: '临近触发',
      tone: 'norm',
      sentence: `${stock} 临近触发区，继续盯盘`,
      meta: metaBase(item),
    }
  }
  if (item.l0Verdict === 'degraded') {
    return {
      key: item.id,
      time,
      stockCode: item.stockCode,
      tag: '体检告警',
      tone: 'norm',
      sentence: `计划体检告警：${item.l0Detail ?? '与盘面脱锚'}`,
      meta: metaBase(item),
    }
  }
  return {
    key: item.id,
    time,
    stockCode: item.stockCode,
    tag: '心跳',
    tone: 'dim',
    sentence: `盯着${stock}的分时，按兵不动`,
    meta: metaBase(item),
  }
}
