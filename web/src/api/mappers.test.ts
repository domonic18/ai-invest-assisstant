import { describe, expect, it } from 'vitest'

import {
  mapAdminAiResult,
  mapAdminAiResultDetail,
  mapAdminAiSkill,
  mapAuthResponse,
  mapChainAlert,
  mapChainAnalysisResult,
  mapCollectorLog,
  mapIndexQuote,
  mapKlineData,
  mapLLMConfig,
  mapLimitUpData,
  mapMarketReview,
  mapSectorOverview,
  mapStock,
  mapTelegraph,
  mapUser,
  mapWatchlistItem,
  mapWatchlistQuote,
} from './mappers'

import type {
  ApiAdminAiResultDetail,
  ApiAdminAiResultItem,
  ApiAdminAiSkillInfo,
  ApiAuthResponse,
  ApiChainAlert,
  ApiChainAnalysisResult,
  ApiCollectorLogResponse,
  ApiIndexQuoteResponse,
  ApiKlineDataResponse,
  ApiLLMConfigResponse,
  ApiLimitUpResponse,
  ApiMarketReviewResponse,
  ApiSectorOverviewResponse,
  ApiStockBasicResponse,
  ApiUserResponse,
  ApiWatchlistItemResponse,
  ApiWatchlistQuoteItem,
} from '@ai-invest/shared'

describe('mappers', () => {
  it('maps user', () => {
    const dto: ApiUserResponse = {
      id: 1,
      username: 'tester',
      email: 'test@example.com',
      role: 'admin',
      isActive: true,
      lastLoginAt: null,
      createdAt: '2024-01-01T00:00:00Z',
    }
    const user = mapUser(dto)
    expect(user.id).toBe('1')
    expect(user.isAdmin).toBe(true)
  })

  it('maps auth response', () => {
    const dto: ApiAuthResponse = {
      accessToken: 'token',
      tokenType: 'bearer',
      user: {
        id: 1,
        username: 'tester',
        email: 'test@example.com',
        role: 'user',
        isActive: true,
        lastLoginAt: null,
        createdAt: '2024-01-01T00:00:00Z',
      },
    }
    const result = mapAuthResponse(dto)
    expect(result.accessToken).toBe('token')
    expect(result.user.username).toBe('tester')
  })

  it('maps stock', () => {
    const dto: ApiStockBasicResponse = {
      stockCode: '000001',
      stockName: '平安银行',
      market: 'sz',
      fullName: '平安银行股份有限公司',
      industryLevel1: '金融',
      industryLevel2: '银行',
      industryLevel3: '股份制银行',
      listingDate: '1991-04-03',
      totalShares: null,
      circulatingShares: null,
    }
    const stock = mapStock(dto)
    expect(stock.code).toBe('000001')
    expect(stock.name).toBe('平安银行')
    expect(stock.market).toBe('SZ')
  })

  it('maps kline data', () => {
    const dto: ApiKlineDataResponse = {
      tradeDate: '2024-01-01',
      open: 10,
      high: 11,
      low: 9,
      close: 10.5,
      volume: 1000,
      amount: 10000,
      amplitude: 5,
      changePct: 2,
      turnoverRate: 1.5,
    }
    const item = mapKlineData(dto)
    expect(item.date).toBe('2024-01-01')
    expect(item.close).toBe(10.5)
  })

  it('maps watchlist item', () => {
    const dto: ApiWatchlistItemResponse = {
      id: 1,
      stockCode: '000001',
      tags: ['金融'],
      groupId: 7,
      createdAt: '2024-01-01T00:00:00Z',
    }
    const item = mapWatchlistItem(dto)
    expect(item.id).toBe('1')
    expect(item.groupId).toBe(7)
    expect(item.tags).toEqual(['金融'])
  })

  it('maps chain analysis result', () => {
    const dto: ApiChainAnalysisResult = {
      nodes: [
        {
          name: '硅材料',
          type: 'upstream',
          description: '高纯度硅片',
          companies: [{ code: '123', name: 'Test' }],
          avgGrossMargin: 10,
          revenueGrowth: 5,
          rdRatio: 8.5,
          bargainingPower: 7,
          localizationRate: 40,
          techBarrier: 'high',
          bottleneckIndicators: ['高端硅片依赖进口'],
          recentBreakthroughs: ['良率突破'],
        },
      ],
      edges: [
        {
          source: '硅材料',
          target: '晶圆制造',
          relation: '供应',
          strength: 0.8,
          criticality: 'high',
        },
      ],
      summary: 'summary',
      valueDistribution: {
        highestMarginSegment: '芯片设计',
        highestMarginValue: 45.2,
        lowestMarginSegment: '封装测试',
        lowestMarginValue: 18.5,
      },
      opportunities: [
        { title: 'op1', description: 'desc', relatedSegment: '设备', confidence: 'high' },
      ],
      risks: [
        { title: 'risk1', description: 'desc', relatedSegment: null, severity: 'high' },
      ],
      keyCompaniesSummary: [
        { code: '688981', name: '中芯国际', chainPosition: '晶圆制造', score: 85 },
      ],
    }
    const result = mapChainAnalysisResult(dto)
    expect(result.nodes[0].avgGrossMargin).toBe(10)
    expect(result.nodes[0].localizationRate).toBe(40)
    expect(result.nodes[0].bottleneckIndicators).toEqual(['高端硅片依赖进口'])
    expect(result.edges[0].strength).toBe(0.8)
    expect(result.edges[0].criticality).toBe('high')
    expect(result.opportunities[0].title).toBe('op1')
    expect(result.risks[0].severity).toBe('high')
    expect(result.valueDistribution?.highestMarginSegment).toBe('芯片设计')
    expect(result.keyCompaniesSummary[0].score).toBe(85)
  })

  it('maps chain alert', () => {
    const dto: ApiChainAlert = {
      industry: '半导体',
      alertType: '技术突破',
      severity: 3,
      title: '先进制程良率突破',
      description: '头部代工厂 3nm 良率爬坡超预期',
      affectedSegments: ['晶圆制造'],
      relatedStockCodes: ['688981'],
      signalDate: '2026-08-29',
      createdAt: '2026-08-29T06:05:00+08:00',
    }
    const alert = mapChainAlert(dto)
    expect(alert.industry).toBe('半导体')
    expect(alert.alertType).toBe('技术突破')
    expect(alert.severity).toBe(3)
    expect(alert.title).toBe('先进制程良率突破')
    expect(alert.affectedSegments).toEqual(['晶圆制造'])
    expect(alert.relatedStockCodes).toEqual(['688981'])
    expect(alert.signalDate).toBe('2026-08-29')
  })

  it('maps chain alert with missing optional arrays', () => {
    const alert = mapChainAlert({
      industry: '光伏',
      alertType: '政策催化',
      severity: 1,
      title: '补贴政策落地',
      description: '',
      affectedSegments: null as unknown as string[],
      relatedStockCodes: null as unknown as string[],
      signalDate: '2026-08-29',
      createdAt: '2026-08-29T06:05:00+08:00',
    })
    expect(alert.affectedSegments).toEqual([])
    expect(alert.relatedStockCodes).toEqual([])
    expect(alert.description).toBe('')
  })

  it('maps LLM config', () => {
    const dto: ApiLLMConfigResponse = {
      id: 1,
      name: 'OpenAI GPT-4o',
      provider: 'openai',
      baseUrl: 'https://api.openai.com/v1',
      modelName: 'gpt-4o',
      apiKeyMasked: 'sk-te************************st',
      isDefault: true,
      isActive: true,
      extra: {},
      lastTestedAt: '2024-01-01T00:00:00Z',
      lastTestStatus: 'success',
      lastTestError: null,
      createdAt: '2024-01-01T00:00:00Z',
      updatedAt: '2024-01-01T00:00:00Z',
    }
    const result = mapLLMConfig(dto)
    expect(result.id).toBe(1)
    expect(result.baseUrl).toBe('https://api.openai.com/v1')
    expect(result.modelName).toBe('gpt-4o')
    expect(result.isDefault).toBe(true)
  })

  it('maps collector log', () => {
    const dto: ApiCollectorLogResponse = {
      id: 1,
      taskName: 'kline',
      source: 'sina',
      status: 'success',
      startedAt: '2024-01-01T00:00:00Z',
      finishedAt: '2024-01-01T00:01:00Z',
      recordsCount: 100,
      errorMsg: null,
      metadata: {},
    }
    const result = mapCollectorLog(dto)
    expect(result.taskName).toBe('kline')
    expect(result.source).toBe('sina')
    expect(result.recordsCount).toBe(100)
  })

  it('maps admin ai skill info', () => {
    const dto: ApiAdminAiSkillInfo = {
      skillId: 'market-daily-review',
      label: '大盘每日复盘',
      eventType: 'market_daily_review.complete',
    }
    const skill = mapAdminAiSkill(dto)
    expect(skill.skillId).toBe('market-daily-review')
    expect(skill.label).toBe('大盘每日复盘')
    expect(skill.eventType).toBe('market_daily_review.complete')
  })

  it('maps admin ai result item and detail', () => {
    const dto: ApiAdminAiResultItem = {
      id: 7,
      skillId: 'market-daily-review',
      keyFields: [{ name: 'trade_date', label: '交易日', value: '2026-09-04' }],
      model: 'anthropic/kimi',
      latencyMs: 59000,
      status: 'success',
      createdAt: '2026-09-05T08:00:00Z',
      historyCount: 3,
      regeneratePrompt: '请重新生成 2026-09-04 的大盘每日复盘',
    }
    const item = mapAdminAiResult(dto)
    expect(item.id).toBe(7)
    expect(item.skillId).toBe('market-daily-review')
    expect(item.keyFields[0]).toEqual({ name: 'trade_date', label: '交易日', value: '2026-09-04' })
    expect(item.latencyMs).toBe(59000)
    expect(item.historyCount).toBe(3)
    expect(item.regeneratePrompt).toBe('请重新生成 2026-09-04 的大盘每日复盘')

    const detailDto: ApiAdminAiResultDetail = {
      ...dto,
      errorMsg: null,
      structuredOutput: { tradeDate: '2026-09-04', sections: {} },
    }
    const detail = mapAdminAiResultDetail(detailDto)
    expect(detail.errorMsg).toBeNull()
    expect(detail.structuredOutput).toEqual({ tradeDate: '2026-09-04', sections: {} })
  })

  it('maps index quote', () => {
    const dto: ApiIndexQuoteResponse = {
      code: 'sh000001',
      name: '上证指数',
      price: 3200.5,
      change: 15.2,
      changePct: 0.48,
      amount: 450000000000,
      trend: [3180, 3190, 3200],
    }
    const quote = mapIndexQuote(dto)
    expect(quote.code).toBe('sh000001')
    expect(quote.changePct).toBe(0.48)
    expect(quote.trend).toEqual([3180, 3190, 3200])
  })

  it('maps limit-up data with nested groups', () => {
    const stock = {
      stockCode: '000001',
      stockName: '平安银行',
      changePct: 10.01,
      latestPrice: 12.5,
      sealedAmount: 200000000,
      firstSealTime: '09:25:00',
      lastSealTime: '14:50:00',
      brokenLimitCount: 1,
      limitStatus: '连板',
      consecutiveBoards: 2,
      industry: '银行',
      sealType: 'T字板',
      themes: ['金融'],
    }
    const dto: ApiLimitUpResponse = {
      tradeDate: '2026-09-04',
      total: 45,
      firstBoard: 30,
      continuous: 15,
      maxBoards: 5,
      ladder: [stock],
      items: [stock],
      groups: [
        {
          name: '银行',
          count: 3,
          changePct: 2.5,
          mainNetInflow: 1.2e9,
          reason: '降准利好',
          items: [stock],
        },
      ],
      aiGenerated: true,
    }
    const data = mapLimitUpData(dto)
    expect(data.total).toBe(45)
    expect(data.ladder[0].consecutiveBoards).toBe(2)
    expect(data.groups[0].items[0].stockCode).toBe('000001')
    expect(data.groups[0].reason).toBe('降准利好')
  })

  it('maps sector overview arrays', () => {
    const dto: ApiSectorOverviewResponse = {
      tradeDate: '2026-09-04',
      heatmap: [{ sectorName: '半导体', changePct: 3.2 }],
      topInflow: [{ sectorName: '半导体', mainNetInflow: 5e9, topStockName: '中芯国际' }],
      topOutflow: [{ sectorName: '银行', mainNetInflow: -2e9, topStockName: '招商银行' }],
      leading: [
        {
          sectorName: '半导体',
          changePct: 3.2,
          limitUpCount: 8,
          mainNetInflow: 5e9,
          topStockNames: ['中芯国际'],
        },
      ],
    }
    const overview = mapSectorOverview(dto)
    expect(overview.heatmap[0].sectorName).toBe('半导体')
    expect(overview.topOutflow[0].mainNetInflow).toBe(-2e9)
    expect(overview.leading[0].topStockNames).toEqual(['中芯国际'])
  })

  it('maps watchlist quote with null trend fallback', () => {
    const dto: ApiWatchlistQuoteItem = {
      code: '600519',
      name: '贵州茅台',
      price: 1500,
      changePct: -0.5,
      amount: 2e9,
      tags: ['白酒'],
      updatedAt: '2026-09-04T15:00:00+08:00',
      trend: null as unknown as number[],
    }
    const quote = mapWatchlistQuote(dto)
    expect(quote.code).toBe('600519')
    expect(quote.trend).toEqual([])
  })

  it('maps market review sections', () => {
    const dto: ApiMarketReviewResponse = {
      tradeDate: '2026-09-04',
      sections: [
        { key: 'market_overview', title: '大盘总览', content: '指数震荡上行' },
      ],
      model: 'anthropic/kimi',
      generatedAt: '2026-09-04T16:30:00+08:00',
      cached: false,
      edited: true,
    }
    const review = mapMarketReview(dto)
    expect(review.sections[0].key).toBe('market_overview')
    expect(review.edited).toBe(true)
  })
})

describe('mapTelegraph', () => {
  it('maps aiScore with null fallback for unscored items', () => {
    expect(
      mapTelegraph({
        clsMsgId: 1899921,
        title: null,
        content: '正文',
        category: null,
        importance: null,
        shared: null,
        stockCodes: null,
        publishTime: '2026-09-08T04:00:00Z',
        aiScore: 82,
        aiScoredAt: '2026-09-08T04:05:00Z',
      }).aiScore,
    ).toBe(82)
    expect(
      mapTelegraph({
        clsMsgId: 1899920,
        title: null,
        content: null,
        category: null,
        importance: null,
        shared: null,
        stockCodes: null,
        publishTime: '2026-09-08T03:00:00Z',
      }).aiScore,
    ).toBeNull()
  })
})
