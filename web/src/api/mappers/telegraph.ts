import type {
  ApiTelegraphPage,
  ApiTelegraphResponse,
  TelegraphItem,
  TelegraphPage,
} from '@ai-invest/shared'

export function mapTelegraph(dto: ApiTelegraphResponse): TelegraphItem {
  return {
    clsMsgId: dto.clsMsgId,
    title: dto.title,
    content: dto.content,
    category: dto.category,
    importance: dto.importance,
    shared: dto.shared,
    stockCodes: dto.stockCodes ?? [],
    publishTime: dto.publishTime,
    sourceUrl: `https://www.cls.cn/detail/${dto.clsMsgId}`,
    aiScore: dto.aiScore ?? null,
    aiFactors: dto.aiFactors ?? null,
    subscribed: dto.subscribed ?? false,
  }
}

export function mapTelegraphPage(dto: ApiTelegraphPage): TelegraphPage {
  return {
    total: dto.total,
    page: dto.page,
    pageSize: dto.pageSize,
    items: dto.items.map(mapTelegraph),
  }
}
