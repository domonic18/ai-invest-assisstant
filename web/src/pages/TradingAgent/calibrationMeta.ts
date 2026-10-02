/**
 * 盘中计划校准修正单的中文 META 映射（§11.5，PlanPanel 校准历史共用）。
 * 值域与后端 agent_trade_plan_amendment 列约束对齐（批次 plan-quality-guard）。
 */
import type {
  TradingAgentPlanAmendmentAction,
  TradingAgentPlanAmendmentStatus,
} from '@ai-invest/shared'

export const CALIBRATION_WINDOW_LABELS: Record<string, string> = {
  '1020': '早盘校准',
  '1320': '午盘校准',
}

export const AMENDMENT_ACTION_META: Record<
  TradingAgentPlanAmendmentAction,
  { label: string; color: string }
> = {
  maintain: { label: '维持', color: 'default' },
  adjust: { label: '调整', color: 'processing' },
  cancel: { label: '取消', color: 'error' },
  add: { label: '新增', color: 'success' },
}

export const AMENDMENT_STATUS_META: Record<
  TradingAgentPlanAmendmentStatus,
  { label: string; color: string }
> = {
  applied: { label: '已生效', color: 'success' },
  shadow: { label: '影子留痕', color: 'gold' },
  rejected: { label: '已拒绝', color: 'error' },
}
