import { describe, expect, it } from 'vitest'

import {
  mapAdminAiResult,
  mapAdminAiResultDetail,
  mapAdminAiSkill,
  mapAuthResponse,
  mapChainAlert,
  mapChainAnalysisResult,
  mapCollectorLog,
  mapKlineData,
  mapLLMConfig,
  mapStock,
  mapUser,
  mapWatchlistItem,
} from './mappers'

import type {
  ApiAdminAiResultDetail,
  ApiAdminAiResultItem,
  ApiAdminAiSkillInfo,
  ApiAuthResponse,
  ApiChainAlert,
  ApiChainAnalysisResult,
  ApiCollectorLogResponse,
  ApiKlineDataResponse,
  ApiLLMConfigResponse,
  ApiStockBasicResponse,
  ApiUserResponse,
  ApiWatchlistItemResponse,
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
})
