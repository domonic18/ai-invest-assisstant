import type { ApiPaginatedResponse } from '@ai-invest/shared'

export function mapPaginatedResponse<T, R>(
  dto: ApiPaginatedResponse<T>,
  mapper: (item: T) => R
): { total: number; page: number; pageSize: number; items: R[] } {
  return {
    total: dto.total,
    page: dto.page,
    pageSize: dto.page_size,
    items: dto.items.map(mapper),
  }
}
