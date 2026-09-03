import { describe, expect, it } from 'vitest'

import { mapGlobalIndexQuote, mapSectorFlowItem, mapWorkbench } from './workbench'

import type {
  ApiCalendarEventResponse,
  ApiGlobalIndexQuoteResponse,
  ApiIndexQuoteResponse,
  ApiMarketReviewResponse,
  ApiMarketStatsResponse,
  ApiWorkbenchSectorFlowItem,
  ApiTelegraphResponse,
  ApiWorkbenchResponse,
  ApiWorkbenchWatchlistGroup,
} from '@ai-invest/shared'

const calendarDto: ApiCalendarEventResponse = {
  id: 1,
  event_time: '2026-09-04T10:00:00+08:00',
  end_time: null,
  title: '美联储议息会议',
  category: '央行动态',
  impact_markets: ['美股'],
  source: '官方日程',
  source_url: null,
  related_symbols: null,
}

const reviewDto: ApiMarketReviewResponse = {
  trade_date: '2026-09-02',
  sections: [{ key: 'overview', title: '大盘综述', content: '**缩量反弹**' }],
  model: 'kimi',
  generated_at: '2026-09-02T16:00:00+08:00',
  cached: true,
  edited: false,
}

const telegraphDto: ApiTelegraphResponse = {
  cls_msg_id: 99,
  title: '央行开展逆回购',
  content: '操作量 3000 亿元',
  category: '宏观',
  importance: 3,
  shared: 12,
  stock_codes: null,
  publish_time: '2026-09-03T09:30:00+08:00',
}

const watchlistGroupDto: ApiWorkbenchWatchlistGroup = {
  id: 1,
  name: '核心持仓',
  is_default: false,
  ai_review_enabled: true,
  items: [
    {
      code: '600519',
      name: '贵州茅台',
      price: 1500.5,
      change_pct: 1.2,
      amount: 3500000000,
      tags: [],
      updated_at: '2026-09-03T15:00:00+08:00',
      trend: [1495, 1500.5],
      ai_status: 'ready',
      ai_summary: '沿 MA5 上行，持仓为主',
    },
  ],
}

const indexDto: ApiIndexQuoteResponse = {
  code: 'sh000001',
  name: '上证指数',
  price: 3250.5,
  change: 12.3,
  change_pct: 0.38,
  amount: 320000000000,
  trend: [3240, 3250.5],
}

const statsDto: ApiMarketStatsResponse = {
  trade_date: '2026-09-02',
  amount: 1500000000000,
  prev_amount: null,
  amount_change: null,
  amount_change_pct: null,
  up_count: 3200,
  down_count: 1800,
  flat_count: 200,
  limit_up_count: 65,
  limit_down_count: 3,
  broken_limit_count: 12,
  emotion_score: 55,
  emotion_label: '温和',
  limit_up_ratio: null,
  continuous_rate: null,
  broken_rate: null,
}

const globalDto: ApiGlobalIndexQuoteResponse = {
  index_code: 'XAU',
  index_name: '伦敦金',
  close: 2650.4,
  change_pct: -0.52,
  trade_date: '2026-09-02',
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
    })
  })

  it('keeps null metrics as null', () => {
    const quote = mapGlobalIndexQuote({ ...globalDto, close: null, change_pct: null, trade_date: null })
    expect(quote.close).toBeNull()
    expect(quote.changePct).toBeNull()
    expect(quote.tradeDate).toBeNull()
  })
})

const sectorFlowDto: ApiWorkbenchSectorFlowItem = {
  sector_name: '半导体',
  change_pct: 2.35,
  main_net_inflow: 48.6,
  top_stock_name: '中芯国际',
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
      sector_name: '银行',
      change_pct: null,
      main_net_inflow: null,
      top_stock_name: null,
    })
    expect(item.changePct).toBeNull()
    expect(item.mainNetInflow).toBeNull()
    expect(item.topStockName).toBeNull()
  })
})

describe('mapWorkbench', () => {
  it('maps all eight modules', () => {
    const dto: ApiWorkbenchResponse = {
      calendar: [calendarDto],
      review: reviewDto,
      telegraph: [telegraphDto],
      watchlist_groups: [watchlistGroupDto],
      indices: [indexDto],
      stats: statsDto,
      global_indices: [globalDto],
      sector_flow: [sectorFlowDto],
    }

    const overview = mapWorkbench(dto)
    expect(overview.calendar).toHaveLength(1)
    expect(overview.calendar[0].title).toBe('美联储议息会议')
    expect(overview.review?.tradeDate).toBe('2026-09-02')
    expect(overview.review?.sections[0].content).toBe('**缩量反弹**')
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
  })

  it('passes null review/stats through as null', () => {
    const dto: ApiWorkbenchResponse = {
      calendar: [],
      review: null,
      telegraph: [],
      watchlist_groups: [],
      indices: [],
      stats: null,
      global_indices: [],
      sector_flow: [],
    }

    const overview = mapWorkbench(dto)
    expect(overview.review).toBeNull()
    expect(overview.stats).toBeNull()
    expect(overview.calendar).toEqual([])
    expect(overview.sectorFlow).toEqual([])
  })
})
