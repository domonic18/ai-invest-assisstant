import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiPaginatedResponse,
  ApiSectorFundFlowResponse,
  SectorFundFlow,
} from '@ai-invest/shared'

import { apiClient } from './client'
import { mapPaginatedResponse, mapSectorFundFlow } from './mappers'

/** 与后端 MAX_SECTOR_PAGE_SIZE 对齐：板块资金流是当日有界清单，单页拉全量。 */
const MAX_LIST_PAGE_SIZE = 500

export interface HotspotParams {
  sectorType?: string
  tradeDate?: string
  page?: number
  pageSize?: number
}

export async function fetchHotspots(params: HotspotParams = {}) {
  const response = await apiClient.get<
    ApiPaginatedResponse<ApiSectorFundFlowResponse>
  >(ENDPOINTS.hotspot.list, {
    params: {
      sector_type: params.sectorType,
      trade_date: params.tradeDate,
      page: params.page ?? 1,
      page_size: params.pageSize ?? 20,
    },
  })
  return mapPaginatedResponse(response.data, mapSectorFundFlow)
}

/**
 * 取最新有数据交易日的完整板块清单（话题云 / 信号卡共用）。
 * 列表接口不传日期时按全历史主力净流入排序，最新日小额头板块进不了首页；
 * 故两段式：先探测返回行中的最大交易日，若首页混有历史行再按该日期取全量。
 */
export async function fetchLatestDaySectors(
  pageSize = MAX_LIST_PAGE_SIZE,
): Promise<SectorFundFlow[]> {
  const probe = await fetchHotspots({ page: 1, pageSize })
  if (!probe.items.length) return []
  const tradeDate = probe.items.reduce(
    (latest, item) => (item.tradeDate > latest ? item.tradeDate : latest),
    probe.items[0].tradeDate,
  )
  if (probe.items.every((item) => item.tradeDate === tradeDate)) {
    return probe.items
  }
  const full = await fetchHotspots({ page: 1, pageSize, tradeDate })
  return full.items
}
