import type { ApiResearchReportResponse, ApiSectorFundFlowResponse } from '@ai-invest/shared'
import type { ResearchReport, SectorFundFlow } from '@ai-invest/shared'

export function mapResearchReport(dto: ApiResearchReportResponse): ResearchReport {
  return {
    id: dto.id,
    stockCode: dto.stockCode,
    title: dto.title,
    summary: dto.summary,
    content: dto.content,
    source: dto.source,
    sourceUrl: dto.sourceUrl,
    publishDate: dto.publishDate,
    sentiment: dto.sentiment,
    keywords: dto.keywords,
    industryTags: dto.industryTags,
    extra: dto.extra,
    createdAt: dto.createdAt,
    broker: dto.broker,
    rating: dto.rating,
    pages: dto.pages,
    industry: dto.industry,
    hasSummary: dto.hasSummary,
  }
}

export function mapSectorFundFlow(dto: ApiSectorFundFlowResponse): SectorFundFlow {
  return {
    sectorCode: dto.sectorCode,
    sectorName: dto.sectorName,
    sectorType: dto.sectorType,
    tradeDate: dto.tradeDate,
    changePct: dto.changePct,
    mainNetInflow: dto.mainNetInflow,
    superLargeNet: dto.superLargeNet,
    largeNet: dto.largeNet,
    mediumNet: dto.mediumNet,
    smallNet: dto.smallNet,
    topStockCode: dto.topStockCode,
    topStockName: dto.topStockName,
    createdAt: dto.createdAt,
  }
}
