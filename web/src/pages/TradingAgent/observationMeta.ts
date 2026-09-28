/**
 * 逐 tick 观测行的中文 META 映射（ExecutionTab 与 AgentOverview 实时决策流共用）。
 * 值域与后端 paper_trade_exec_observation 列约束对齐（批次 8 PR-1）。
 */

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
