import { describe, expect, it } from 'vitest'

import {
  mapAuthResponse,
  mapChainAlert,
  mapChainAnalysisResult,
  mapAdminMarketReview,
  mapCollectorLog,
  mapKlineData,
  mapLLMConfig,
  mapStock,
  mapUser,
  mapWatchlistItem,
} from './mappers'

import type {
  ApiAdminMarketReviewItem,
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
      is_active: true,
      last_login_at: null,
      created_at: '2024-01-01T00:00:00Z',
    }
    const user = mapUser(dto)
    expect(user.id).toBe('1')
    expect(user.isAdmin).toBe(true)
  })

  it('maps auth response', () => {
    const dto: ApiAuthResponse = {
      access_token: 'token',
      token_type: 'bearer',
      user: {
        id: 1,
        username: 'tester',
        email: 'test@example.com',
        role: 'user',
        is_active: true,
        last_login_at: null,
        created_at: '2024-01-01T00:00:00Z',
      },
    }
    const result = mapAuthResponse(dto)
    expect(result.accessToken).toBe('token')
    expect(result.user.username).toBe('tester')
  })

  it('maps stock', () => {
    const dto: ApiStockBasicResponse = {
      stock_code: '000001',
      stock_name: '平安银行',
      market: 'sz',
      full_name: '平安银行股份有限公司',
      industry_level_1: '金融',
      industry_level_2: '银行',
      industry_level_3: '股份制银行',
      listing_date: '1991-04-03',
      total_shares: null,
      circulating_shares: null,
    }
    const stock = mapStock(dto)
    expect(stock.code).toBe('000001')
    expect(stock.name).toBe('平安银行')
    expect(stock.market).toBe('SZ')
  })

  it('maps kline data', () => {
    const dto: ApiKlineDataResponse = {
      trade_date: '2024-01-01',
      open: 10,
      high: 11,
      low: 9,
      close: 10.5,
      volume: 1000,
      amount: 10000,
      amplitude: 5,
      change_pct: 2,
      turnover_rate: 1.5,
    }
    const item = mapKlineData(dto)
    expect(item.date).toBe('2024-01-01')
    expect(item.close).toBe(10.5)
  })

  it('maps watchlist item', () => {
    const dto: ApiWatchlistItemResponse = {
      id: 1,
      stock_code: '000001',
      tags: ['金融'],
      group_id: 7,
      created_at: '2024-01-01T00:00:00Z',
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
      base_url: 'https://api.openai.com/v1',
      model_name: 'gpt-4o',
      api_key_masked: 'sk-te************************st',
      is_default: true,
      is_active: true,
      extra: {},
      last_tested_at: '2024-01-01T00:00:00Z',
      last_test_status: 'success',
      last_test_error: null,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
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
      task_name: 'kline',
      source: 'sina',
      status: 'success',
      started_at: '2024-01-01T00:00:00Z',
      finished_at: '2024-01-01T00:01:00Z',
      records_count: 100,
      error_msg: null,
      metadata: {},
    }
    const result = mapCollectorLog(dto)
    expect(result.taskName).toBe('kline')
    expect(result.source).toBe('sina')
    expect(result.recordsCount).toBe(100)
  })

  it('maps admin market review item', () => {
    const dto: ApiAdminMarketReviewItem = {
      trade_date: '2026-09-04',
      model: 'anthropic/kimi',
      latency_ms: 59000,
      generated_at: '2026-09-05T08:00:00Z',
      history_count: 3,
      user_copy_count: 1,
    }
    const item = mapAdminMarketReview(dto)
    expect(item.tradeDate).toBe('2026-09-04')
    expect(item.model).toBe('anthropic/kimi')
    expect(item.latencyMs).toBe(59000)
    expect(item.historyCount).toBe(3)
    expect(item.userCopyCount).toBe(1)
  })
})
