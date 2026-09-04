import type { ApiResearchReportResponse, ApiSectorFundFlowResponse } from '@ai-invest/shared'
import type { ResearchReport, SectorFundFlow } from '@ai-invest/shared'

export function mapResearchReport(dto: ApiResearchReportResponse): ResearchReport {
  return {
    id: dto.id,
    stockCode: dto.stock_code,
    title: dto.title,
    summary: dto.summary,
    content: dto.content,
    source: dto.source,
    sourceUrl: dto.source_url,
    publishDate: dto.publish_date,
    sentiment: dto.sentiment,
    keywords: dto.keywords,
    industryTags: dto.industry_tags,
    extra: dto.extra,
    createdAt: dto.created_at,
    broker: dto.broker,
    rating: dto.rating,
    pages: dto.pages,
    industry: dto.industry,
    hasSummary: dto.has_summary,
  }
}

export function mapSectorFundFlow(dto: ApiSectorFundFlowResponse): SectorFundFlow {
  return {
    sectorCode: dto.sector_code,
    sectorName: dto.sector_name,
    sectorType: dto.sector_type,
    tradeDate: dto.trade_date,
    changePct: dto.change_pct,
    mainNetInflow: dto.main_net_inflow,
    superLargeNet: dto.super_large_net,
    largeNet: dto.large_net,
    mediumNet: dto.medium_net,
    smallNet: dto.small_net,
    topStockCode: dto.top_stock_code,
    topStockName: dto.top_stock_name,
    createdAt: dto.created_at,
  }
}
