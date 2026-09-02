import type {
  ApiTelegraphPage,
  ApiTelegraphResponse,
  TelegraphItem,
  TelegraphPage,
} from '@ai-invest/shared'

export function mapTelegraph(dto: ApiTelegraphResponse): TelegraphItem {
  return {
    clsMsgId: dto.cls_msg_id,
    title: dto.title,
    content: dto.content,
    category: dto.category,
    importance: dto.importance,
    shared: dto.shared,
    stockCodes: dto.stock_codes ?? [],
    publishTime: dto.publish_time,
    sourceUrl: `https://www.cls.cn/detail/${dto.cls_msg_id}`,
  }
}

export function mapTelegraphPage(dto: ApiTelegraphPage): TelegraphPage {
  return {
    total: dto.total,
    page: dto.page,
    pageSize: dto.page_size,
    items: dto.items.map(mapTelegraph),
  }
}
