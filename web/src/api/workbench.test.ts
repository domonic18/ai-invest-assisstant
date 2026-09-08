import { describe, expect, it } from 'vitest'

import {
  mapCollectorStatus,
  mapGlobalIndexQuote,
  mapReviewStatus,
  mapSectorFlowItem,
  mapWorkbench,
} from './mappers/workbench'

import type {
  ApiCalendarEventResponse,
  ApiCollectorEngineStatus,
  ApiGlobalIndexQuoteResponse,
  ApiIndexQuoteResponse,
  ApiMarketReviewResponse,
  ApiMarketStatsResponse,
  ApiReviewStatus,
  ApiWorkbenchSectorFlowItem,
  ApiTelegraphResponse,
  ApiWorkbenchResponse,
  ApiWorkbenchWatchlistGroup,
} from '@ai-invest/shared'

const calendarDto: ApiCalendarEventResponse = {
  id: 1,
  eventTime: '2026-09-04T10:00:00+08:00',
  endTime: null,
  title: '美联储议息会议',
  category: '央行动态',
  impactMarkets: ['美股'],
  source: '官方日程',
  sourceUrl: null,
  relatedSymbols: null,
}

const reviewDto: ApiMarketReviewResponse = {
  tradeDate: '2026-09-02',
  sections: [{ key: 'overview', title: '大盘综述', content: '**缩量反弹**' }],
  model: 'kimi',
  generatedAt: '2026-09-02T16:00:00+08:00',
  cached: true,
  edited: false,
}

const telegraphDto: ApiTelegraphResponse = {
  clsMsgId: 99,
  title: '央行开展逆回购',
  content: '操作量 3000 亿元',
  category: '宏观',
  importance: 3,
  shared: 12,
  stockCodes: null,
  publishTime: '2026-09-03T09:30:00+08:00',
}

const watchlistGroupDto: ApiWorkbenchWatchlistGroup = {
  id: 1,
  name: '核心持仓',
  isDefault: false,
  aiReviewEnabled: true,
  items: [
    {
      code: '600519',
      name: '贵州茅台',
      price: 1500.5,
      changePct: 1.2,
      amount: 3500000000,
      tags: [],
      updatedAt: '2026-09-03T15:00:00+08:00',
      trend: [1495, 1500.5],
      aiStatus: 'ready',
      aiSummary: '沿 MA5 上行，持仓为主',
    },
  ],
}

const indexDto: ApiIndexQuoteResponse = {
  code: 'sh000001',
  name: '上证指数',
  price: 3250.5,
  change: 12.3,
  changePct: 0.38,
  amount: 320000000000,
  trend: [3240, 3250.5],
}

const statsDto: ApiMarketStatsResponse = {
  tradeDate: '2026-09-02',
  amount: 1500000000000,
  prevAmount: null,
  amountChange: null,
  amountChangePct: null,
  upCount: 3200,
  downCount: 1800,
  flatCount: 200,
  limitUpCount: 65,
  limitDownCount: 3,
  brokenLimitCount: 12,
  emotionScore: 55,
  emotionLabel: '温和',
  limitUpRatio: null,
  continuousRate: null,
  brokenRate: null,
}

const globalDto: ApiGlobalIndexQuoteResponse = {
  indexCode: 'XAU',
  indexName: '伦敦金',
  close: 2650.4,
  changePct: -0.52,
  tradeDate: '2026-09-02',
  trend: [2648.1, 2650.4],
}

describe('mapGlobalIndexQuote', () => {
  it('maps fields to camelCase', () => {
    const quote = mapGlobalIndexQuote(globalDto)
    expect(quote).toEqual({
      indexCode: 'XAU',
      indexName: '伦敦金',
      close: 2650.4,
      changePct: -0.52,
      tradeDate: '2026-09-02',
      trend: [2648.1, 2650.4],
    })
  })

  it('keeps null metrics as null', () => {
    const quote = mapGlobalIndexQuote({ ...globalDto, close: null, changePct: null, tradeDate: null })
    expect(quote.close).toBeNull()
    expect(quote.changePct).toBeNull()
    expect(quote.tradeDate).toBeNull()
  })
})

const sectorFlowDto: ApiWorkbenchSectorFlowItem = {
  sectorName: '半导体',
  changePct: 2.35,
  mainNetInflow: 48.6,
  topStockName: '中芯国际',
}

describe('mapSectorFlowItem', () => {
  it('maps fields to camelCase', () => {
    expect(mapSectorFlowItem(sectorFlowDto)).toEqual({
      sectorName: '半导体',
      changePct: 2.35,
      mainNetInflow: 48.6,
      topStockName: '中芯国际',
    })
  })

  it('keeps null metrics as null', () => {
    const item = mapSectorFlowItem({
      sectorName: '银行',
      changePct: null,
      mainNetInflow: null,
      topStockName: null,
    })
    expect(item.changePct).toBeNull()
    expect(item.mainNetInflow).toBeNull()
    expect(item.topStockName).toBeNull()
  })
})

const reviewStatusDto: ApiReviewStatus = {
  status: 'done',
  tradeDate: '2026-09-04',
  generatedAt: '2026-09-04T08:32:00+00:00',
  durationSeconds: 134,
  plannedTime: '16:30',
  nextRunAt: '2026-09-07T08:30:00+00:00',
  streakDays: 3,
  monthSuccessRate: 96.4,
  recentDays: [
    { tradeDate: '2026-09-04', status: 'success' },
    { tradeDate: '2026-09-03', status: 'failed' },
    { tradeDate: '2026-09-02', status: 'pending' },
  ],
}

describe('mapReviewStatus', () => {
  it('maps fields to camelCase', () => {
    const status = mapReviewStatus(reviewStatusDto)
    expect(status.status).toBe('done')
    expect(status.tradeDate).toBe('2026-09-04')
    expect(status.durationSeconds).toBe(134)
    expect(status.plannedTime).toBe('16:30')
    expect(status.streakDays).toBe(3)
    expect(status.monthSuccessRate).toBe(96.4)
    expect(status.recentDays[1]).toEqual({ tradeDate: '2026-09-03', status: 'failed' })
  })
})

const collectorStatusDto: ApiCollectorEngineStatus = {
  isRunning: true,
  running: {
    taskName: 'sina_quote',
    taskLabel: '实时行情',
    source: 'sina',
    status: 'running',
    startedAt: '2026-09-04T06:59:00+00:00',
    finishedAt: null,
    durationSeconds: null,
    recordsCount: null,
  },
  recentRuns: [
    {
      taskName: 'market-breadth',
      taskLabel: '涨跌统计',
      source: 'sina',
      status: 'SUCCESS',
      startedAt: '2026-09-04T07:55:00+00:00',
      finishedAt: '2026-09-04T07:55:32+00:00',
      durationSeconds: 32,
      recordsCount: 1240,
    },
  ],
  upcoming: [
    {
      runAt: '2026-09-04T08:00:00+00:00',
      taskName: 'eastmoney_limit_up_pool',
      taskLabel: '涨停股池',
      source: 'eastmoney',
    },
  ],
}

describe('mapCollectorStatus', () => {
  it('maps running/recent/upcoming to camelCase', () => {
    const status = mapCollectorStatus(collectorStatusDto)
    expect(status.isRunning).toBe(true)
    expect(status.running?.taskLabel).toBe('实时行情')
    expect(status.running?.finishedAt).toBeNull()
    expect(status.recentRuns[0].recordsCount).toBe(1240)
    expect(status.upcoming[0].runAt).toBe('2026-09-04T08:00:00+00:00')
  })

  it('keeps null running as null', () => {
    const status = mapCollectorStatus({
      isRunning: false,
      running: null,
      recentRuns: [],
      upcoming: [],
    })
    expect(status.running).toBeNull()
    expect(status.recentRuns).toEqual([])
  })
})

describe('mapWorkbench', () => {
  it('maps all modules', () => {
    const dto: ApiWorkbenchResponse = {
      calendar: [calendarDto],
      review: reviewDto,
      reviewStatus: reviewStatusDto,
      telegraph: [telegraphDto],
      watchlistGroups: [watchlistGroupDto],
      indices: [indexDto],
      stats: statsDto,
      globalIndices: [globalDto],
      sectorFlow: [sectorFlowDto],
      collectorStatus: collectorStatusDto,
    }

    const overview = mapWorkbench(dto)
    expect(overview.calendar).toHaveLength(1)
    expect(overview.calendar[0].title).toBe('美联储议息会议')
    expect(overview.review?.tradeDate).toBe('2026-09-02')
    expect(overview.review?.sections[0].content).toBe('**缩量反弹**')
    expect(overview.reviewStatus?.status).toBe('done')
    expect(overview.reviewStatus?.recentDays[0].tradeDate).toBe('2026-09-04')
    expect(overview.telegraph).toHaveLength(1)
    expect(overview.telegraph[0].clsMsgId).toBe(99)
    expect(overview.watchlistGroups[0].name).toBe('核心持仓')
    expect(overview.watchlistGroups[0].items[0].code).toBe('600519')
    expect(overview.watchlistGroups[0].items[0].aiStatus).toBe('ready')
    expect(overview.watchlistGroups[0].items[0].aiSummary).toBe('沿 MA5 上行，持仓为主')
    expect(overview.indices[0].code).toBe('sh000001')
    expect(overview.stats?.emotionScore).toBe(55)
    expect(overview.globalIndices[0].indexName).toBe('伦敦金')
    expect(overview.sectorFlow[0].sectorName).toBe('半导体')
    expect(overview.sectorFlow[0].mainNetInflow).toBe(48.6)
    expect(overview.collectorStatus?.isRunning).toBe(true)
    expect(overview.collectorStatus?.upcoming[0].taskLabel).toBe('涨停股池')
  })

  it('passes null review/stats/collector through as null', () => {
    const dto: ApiWorkbenchResponse = {
      calendar: [],
      review: null,
      reviewStatus: null,
      telegraph: [],
      watchlistGroups: [],
      indices: [],
      stats: null,
      globalIndices: [],
      sectorFlow: [],
      collectorStatus: null,
    }

    const overview = mapWorkbench(dto)
    expect(overview.review).toBeNull()
    expect(overview.stats).toBeNull()
    expect(overview.reviewStatus).toBeNull()
    expect(overview.collectorStatus).toBeNull()
    expect(overview.calendar).toEqual([])
    expect(overview.sectorFlow).toEqual([])
  })
})
