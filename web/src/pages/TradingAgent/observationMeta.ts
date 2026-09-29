/**
 * 逐 tick 观测行的中文 META 映射与结论合成（ExecutionTab 与 AgentOverview
 * 实时决策流共用）。值域与后端 paper_trade_exec_observation 列约束对齐
 * （批次 8 PR-1）。
 */
import type { ApiTradingAgentObservationItem } from '@ai-invest/shared'

export const VERDICT_META: Record<string, { label: string; color: string }> = {
  no_action: { label: '无动作', color: 'default' },
  near_trigger: { label: '临近触发', color: 'gold' },
  triggered: { label: '已触发', color: 'processing' },
  degraded: { label: '降级', color: 'error' },
}

export const TRIGGER_REASON_LABELS: Record<string, string> = {
  buy_zone: '买点区间',
  target: '目标价',
  stop_loss: '止损',
}

export const ACTION_META: Record<string, { label: string; color: string }> = {
  execute: { label: '已执行', color: 'success' },
  wait: { label: '等待', color: 'processing' },
  abandon: { label: '放弃', color: 'default' },
  suppress: { label: '抑制', color: 'warning' },
}

export const SUPPRESSION_META: Record<string, string> = {
  shadow_mode: '影子模式',
  below_threshold: '低于阈值',
  l0_reject: 'L0 拒绝',
  model_degraded: '模型降级',
  risk_rejected: '风控拒绝',
  no_account: '无账户',
  order_error: '下单失败',
  position_unavailable: '持仓不可用',
}

export function fmtPct(value: number | null): string {
  if (value == null) return '-'
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
}

/** 触发短语（triggered 行结论前半句，按触发原因）。 */
const TRIGGER_PHRASES: Record<string, string> = {
  stop_loss: '击穿止损线',
  target: '触及止盈目标',
  buy_zone: '进入买点区间',
}

/** 抑制/拦截原因 → 一句话后果（triggered 行结论后半句）。 */
const SUPPRESSION_SUMMARY_PHRASES: Record<string, string> = {
  shadow_mode: '影子模式仅记录',
  below_threshold: '置信不足未执行',
  model_degraded: '模型降级仅比价',
  risk_rejected: '风控拒绝下单',
  position_unavailable: '无可交易持仓',
  order_error: '下单失败',
  no_account: '未绑定账户',
}

/** 一句话主结论（按 window × l0Verdict × triggerReason × action × suppression 组合）。 */
export function observationSummary(item: ApiTradingAgentObservationItem): string {
  const detail = item.l0Detail
  const choice = item.decision?.choice

  if (item.decision?.window === 'tail_check') {
    return `尾盘强检：跌破止损${item.action === 'execute' ? '，强制卖出' : '，仅记录'}`
  }
  if (item.l0Verdict === 'no_action') {
    if (item.suppressionReason === 'l0_reject') {
      return `纪律否决：${detail ?? '触发前提失效'}`
    }
    return `巡检正常 · ${detail ?? '未触达触发价'}`
  }
  if (item.l0Verdict === 'near_trigger') {
    return `接近触发 · ${detail ?? '等待回踩'}`
  }
  if (item.l0Verdict === 'degraded') {
    return '模型降级 · 仅按确定性规则巡检'
  }

  const trigger = TRIGGER_PHRASES[item.triggerReason ?? ''] ?? '价格触发'
  if (item.action === 'wait' || item.action === 'abandon') {
    const fallback = item.action === 'wait' ? '等待回踩' : '放弃本档'
    return `${trigger}，模型选择${choice ?? fallback}`
  }
  if (item.suppressionReason) {
    const phrase = SUPPRESSION_SUMMARY_PHRASES[item.suppressionReason] ?? '未实际下单'
    return `${trigger}，${phrase}`
  }
  if (item.action === 'execute') {
    return `${trigger}，已下单执行`
  }
  return trigger
}

/** 盘面支持度分档（score 实际量纲 1-5，与 legend 对齐）。 */
export function scoreBand(score: number): string {
  if (score <= 1.5) return '极弱'
  if (score <= 2.5) return '弱势'
  if (score <= 3.5) return '中性'
  if (score <= 4.5) return '强势'
  return '极强'
}

export function fmtScore(score: number): string {
  return `${score.toFixed(1)}/5 · ${scoreBand(score)}`
}

/** 置信分档（起步阈值语义：<observe 0.6 低 / <fund_action 0.85 中 / 高）。 */
export function confidenceBand(confidence: number): string {
  const pct = confidence * 100
  if (pct < 60) return '低'
  if (pct < 85) return '中'
  return '高'
}

export function fmtConfidence(confidence: number): string {
  return `置信 ${(confidence * 100).toFixed(0)}%（${confidenceBand(confidence)}）`
}

/** 分时形态答案的方向词（noul 按计划方向：sell=离场 / 其余=买入）。 */
export function noulLabel(noul: boolean, planType: 'buy' | 'sell' | null): string {
  const verb = planType === 'sell' ? '离场' : '买入'
  return noul ? `分时：支持${verb}` : `分时：不支持${verb}`
}
