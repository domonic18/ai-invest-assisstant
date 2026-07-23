import { describe, expect, it } from 'vitest'

import {
  mapAuthResponse,
  mapChainAnalysisResult,
  mapCollectorLog,
  mapKlineData,
  mapLLMConfig,
  mapStock,
  mapUser,
  mapWatchlistItem,
} from './mappers'

import type {
  ApiAuthResponse,
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
      industry_level_1: '金融',
      industry_level_2: '银行',
      industry_level_3: '股份制银行',
      listing_date: '1991-04-03',
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
      created_at: '2024-01-01T00:00:00Z',
    }
    const item = mapWatchlistItem(dto)
    expect(item.id).toBe('1')
    expect(item.tags).toEqual(['金融'])
  })

  it('maps chain analysis result', () => {
    const dto: ApiChainAnalysisResult = {
      nodes: [
        {
          name: '硅材料',
          type: 'upstream',
          companies: [{ code: '123', name: 'Test' }],
          avg_gross_margin: 10,
          revenue_growth: 5,
          bargaining_power: 7,
        },
      ],
      edges: [
        { source: '硅材料', target: '晶圆制造', relation: '供应', strength: 0.8 },
      ],
      summary: 'summary',
      opportunities: ['op1'],
      risks: ['risk1'],
    }
    const result = mapChainAnalysisResult(dto)
    expect(result.nodes[0].avgGrossMargin).toBe(10)
    expect(result.edges[0].strength).toBe(0.8)
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
})
