import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiAdminMarketReviewCreateRequest,
  ApiAdminMarketReviewItem,
  ApiAdminMarketReviewSectionsRequest,
  ApiAdminSectionDefinition,
  ApiMarketReviewResponse,
  ApiPaginatedResponse,
  MarketReview,
} from '@ai-invest/shared'

import { apiClient } from './client'
import { mapAdminMarketReview, mapPaginatedResponse } from './mappers'
import { mapMarketReview } from './market'

export interface AdminMarketReviewListParams {
  startDate?: string
  endDate?: string
  page?: number
  pageSize?: number
}

export async function fetchAdminMarketReviews(
  params: AdminMarketReviewListParams = {},
) {
  const response = await apiClient.get<
    ApiPaginatedResponse<ApiAdminMarketReviewItem>
  >(ENDPOINTS.admin.marketReviews, {
    params: {
      start_date: params.startDate,
      end_date: params.endDate,
      page: params.page ?? 1,
      page_size: params.pageSize ?? 20,
    },
  })
  return mapPaginatedResponse(response.data, mapAdminMarketReview)
}

export async function fetchAdminMarketReviewDetail(tradeDate: string): Promise<MarketReview> {
  const response = await apiClient.get<ApiMarketReviewResponse>(
    ENDPOINTS.admin.marketReview(tradeDate),
  )
  return mapMarketReview(response.data)
}

export async function fetchMarketReviewSectionDefinitions(): Promise<
  ApiAdminSectionDefinition[]
> {
  const response = await apiClient.get<ApiAdminSectionDefinition[]>(
    ENDPOINTS.admin.marketReviewSectionDefs,
  )
  return response.data
}

export async function createAdminMarketReview(
  data: ApiAdminMarketReviewCreateRequest,
): Promise<MarketReview> {
  const response = await apiClient.post<ApiMarketReviewResponse>(
    ENDPOINTS.admin.marketReviews,
    data,
  )
  return mapMarketReview(response.data)
}

export async function updateAdminMarketReview(
  tradeDate: string,
  data: ApiAdminMarketReviewSectionsRequest,
): Promise<MarketReview> {
  const response = await apiClient.put<ApiMarketReviewResponse>(
    ENDPOINTS.admin.marketReview(tradeDate),
    data,
  )
  return mapMarketReview(response.data)
}

export async function deleteAdminMarketReview(tradeDate: string) {
  await apiClient.delete(ENDPOINTS.admin.marketReview(tradeDate))
}
