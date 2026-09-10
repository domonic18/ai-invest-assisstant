import type { ApiNewsFlashItem, ApiNewsFlashPage } from '@ai-invest/shared'

/** 东财快讯条目（基础流，wire 与领域同构）。 */
export interface NewsFlashItem {
  id: number
  source: string
  title: string | null
  summary: string | null
  content: string | null
  sourceUrl: string | null
  publishTime: string
}

/** 东财快讯分页领域类型。 */
export interface NewsFlashPage {
  total: number
  page: number
  pageSize: number
  items: NewsFlashItem[]
}

export function mapNewsFlashItem(dto: ApiNewsFlashItem): NewsFlashItem {
  return {
    id: dto.id,
    source: dto.source,
    title: dto.title,
    summary: dto.summary,
    content: dto.content,
    sourceUrl: dto.sourceUrl,
    publishTime: dto.publishTime,
  }
}

export function mapNewsFlashPage(dto: ApiNewsFlashPage): NewsFlashPage {
  return {
    total: dto.total,
    page: dto.page,
    pageSize: dto.pageSize,
    items: dto.items.map(mapNewsFlashItem),
  }
}
