import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiKlineDataResponse,
  ApiPaginatedResponse,
  ApiStockAiAnalysisStatusResponse,
  ApiStockBasicResponse,
  ApiStockIntradayResponse,
  ApiStockKlineResponse,
  ApiStockQuoteResponse,
  ApiStockSectorsResponse,
} from '@ai-invest/shared'
import type { StockAiAnalysis } from '@ai-invest/shared'

import { apiClient } from './client'
import {
  mapIntraday,
  mapKlineData,
  mapPaginatedResponse,
  mapStock,
  mapStockAiAnalysis,
  mapStockKline,
  mapStockQuote,
  mapStockSectors,
} from './mappers'

export interface SearchStocksParams {
  q: string
  limit?: number
}

export interface KlineParams {
  startDate?: string
  endDate?: string
  page?: number
  pageSize?: number
}

export interface StockKlineParams {
  period?: 'daily' | 'weekly' | 'monthly'
  limit?: number
}

export async function searchStocks(params: SearchStocksParams) {
  const response = await apiClient.get<ApiStockBasicResponse[]>(ENDPOINTS.stocks.search, {
    params: { q: params.q, limit: params.limit ?? 20 },
  })
  return response.data.map(mapStock)
}

export async function fetchStockDetail(code: string, market?: string) {
  const response = await apiClient.get<ApiStockBasicResponse>(ENDPOINTS.stocks.detail(code), {
    params: market ? { market } : undefined,
  })
  return mapStock(response.data)
}

export async function fetchStockQuote(code: string) {
  const response = await apiClient.get<ApiStockQuoteResponse>(ENDPOINTS.stocks.quote(code))
  return mapStockQuote(response.data)
}

export async function fetchStockKline(code: string, params: StockKlineParams = {}) {
  const response = await apiClient.get<ApiStockKlineResponse>(ENDPOINTS.stocks.kline(code), {
    params: {
      period: params.period ?? 'daily',
      limit: params.limit ?? 250,
    },
  })
  return mapStockKline(response.data)
}

export async function fetchStockIntraday(code: string, tradeDate?: string) {
  const response = await apiClient.get<ApiStockIntradayResponse>(
    ENDPOINTS.stocks.intraday(code),
    {
      params: tradeDate ? { trade_date: tradeDate } : undefined,
    },
  )
  return mapIntraday(response.data)
}

export async function fetchStockSectors(code: string) {
  const response = await apiClient.get<ApiStockSectorsResponse>(ENDPOINTS.stocks.sectors(code))
  return mapStockSectors(response.data)
}

export interface StockAiAnalysisStatus {
  status: 'running' | 'ready' | 'none'
  data: StockAiAnalysis | null
}

function mapAiAnalysisStatus(dto: ApiStockAiAnalysisStatusResponse): StockAiAnalysisStatus {
  return {
    status: dto.status,
    data: dto.data ? mapStockAiAnalysis(dto.data) : null,
  }
}

/** 读取个股 AI 分析状态（轮询契约）：ready 含数据，running 生成中，none 无结果。 */
export async function fetchStockAiAnalysisStatus(
  code: string,
  tradeDate?: string,
): Promise<StockAiAnalysisStatus> {
  const response = await apiClient.get<ApiStockAiAnalysisStatusResponse>(
    ENDPOINTS.stocks.aiAnalysis(code),
    { params: { trade_date: tradeDate } },
  )
  return mapAiAnalysisStatus(response.data)
}

export async function fetchKline(code: string, params: KlineParams = {}) {
  const response = await apiClient.get<ApiPaginatedResponse<ApiKlineDataResponse>>(
    ENDPOINTS.kline.get(code),
    {
      params: {
        start_date: params.startDate,
        end_date: params.endDate,
        page: params.page ?? 1,
        page_size: params.pageSize ?? 100,
      },
    }
  )
  return mapPaginatedResponse(response.data, mapKlineData)
}
