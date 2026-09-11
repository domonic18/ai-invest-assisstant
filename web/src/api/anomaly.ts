import { ENDPOINTS } from '@ai-invest/shared'
import type {
  AnomalySectorType,
  ApiSectorAnomalyResponse,
  ApiStockAnomalyResponse,
} from '@ai-invest/shared'

import { apiClient } from './client'

/** 板块异动榜（强度降序）；未传日期取最新检测日，无数据返回 undefined。 */
export async function fetchSectorAnomalyBoard(
  tradeDate?: string,
  sectorType?: AnomalySectorType,
): Promise<ApiSectorAnomalyResponse | undefined> {
  const response = await apiClient.get<ApiSectorAnomalyResponse | null>(
    ENDPOINTS.anomaly.sector,
    { params: { trade_date: tradeDate, sector_type: sectorType } },
  )
  return response.data ?? undefined
}

/** 个股异动榜（强度降序，命中自选股带标注）；无数据返回 undefined。 */
export async function fetchStockAnomalyBoard(
  tradeDate?: string,
): Promise<ApiStockAnomalyResponse | undefined> {
  const response = await apiClient.get<ApiStockAnomalyResponse | null>(
    ENDPOINTS.anomaly.stock,
    { params: { trade_date: tradeDate } },
  )
  return response.data ?? undefined
}
