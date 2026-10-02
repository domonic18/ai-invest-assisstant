import type { AgentOverviewItem, AgentRuntimeState } from '@ai-invest/shared'

/** 测试夹具构造：overview item（默认值可被覆盖）。 */
export function makeOverviewItem(
  overrides: Partial<AgentOverviewItem> & { runtimeState?: AgentRuntimeState } = {},
): AgentOverviewItem {
  return {
    profile: {
      agentKey: 'hunter',
      name: '短线猎手',
      tagline: '',
      llmConfigId: null,
      methodologySourceId: null,
      riskMaxPositionPct: 20,
      riskMaxTotalPct: 60,
      riskMaxDailyOrders: 5,
      intradayExecMode: 'shadow',
      intradayPaused: false,
      calibrationMode: 'shadow',
      status: 'active',
      planCadence: 'daily',
      reviewCadence: 'daily',
      sortOrder: 0,
      promptId: 'default',
      accentColor: '#22d3ee',
      updatedAt: null,
    },
    llmName: null,
    runtimeState: 'idle',
    stateLabel: null,
    accountName: null,
    planCount: 0,
    selectionCount: 0,
    orderCount: 0,
    recentActivity: [],
    nextTasks: [],
    ...overrides,
  }
}
