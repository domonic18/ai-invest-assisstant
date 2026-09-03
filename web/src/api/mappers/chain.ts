import type {
  ApiChainAlert,
  ApiChainAnalysisResult,
  ApiChainCompareResult,
  ApiChainEdge,
  ApiChainNode,
  ApiChainVersionDetail,
  ApiChainVersionSummary,
} from '@ai-invest/shared'
import type {
  ChainAlert,
  ChainAlertType,
  ChainAnalysisResult,
  ChainCompareResult,
  ChainEdge,
  ChainNode,
  ChainVersionDetail,
  ChainVersionSummary,
} from '@ai-invest/shared'

export function mapChainAlert(dto: ApiChainAlert): ChainAlert {
  return {
    industry: dto.industry,
    alertType: dto.alertType as ChainAlertType,
    severity: dto.severity,
    title: dto.title,
    description: dto.description || '',
    affectedSegments: dto.affectedSegments || [],
    relatedStockCodes: dto.relatedStockCodes || [],
    signalDate: dto.signalDate,
    createdAt: dto.createdAt,
  }
}

export function mapChainNode(dto: ApiChainNode): ChainNode {
  return {
    name: dto.name,
    type: dto.type,
    description: dto.description || '',
    companies: dto.companies,
    avgGrossMargin: dto.avgGrossMargin,
    revenueGrowth: dto.revenueGrowth,
    rdRatio: dto.rdRatio,
    bargainingPower: dto.bargainingPower,
    localizationRate: dto.localizationRate,
    techBarrier: dto.techBarrier,
    bottleneckIndicators: dto.bottleneckIndicators || [],
    recentBreakthroughs: dto.recentBreakthroughs || [],
  }
}

export function mapChainEdge(dto: ApiChainEdge): ChainEdge {
  return {
    source: dto.source,
    target: dto.target,
    relation: dto.relation,
    strength: Number(dto.strength),
    description: dto.description || '',
    criticality: dto.criticality,
  }
}

export function mapChainAnalysisResult(dto: ApiChainAnalysisResult): ChainAnalysisResult {
  return {
    nodes: dto.nodes.map(mapChainNode),
    edges: dto.edges.map(mapChainEdge),
    summary: dto.summary,
    valueDistribution: dto.valueDistribution
      ? {
          highestMarginSegment: dto.valueDistribution.highestMarginSegment,
          highestMarginValue: dto.valueDistribution.highestMarginValue,
          lowestMarginSegment: dto.valueDistribution.lowestMarginSegment,
          lowestMarginValue: dto.valueDistribution.lowestMarginValue,
        }
      : null,
    opportunities: dto.opportunities.map((item) => ({
      title: item.title,
      description: item.description || '',
      relatedSegment: item.relatedSegment,
      confidence: item.confidence,
    })),
    risks: dto.risks.map((item) => ({
      title: item.title,
      description: item.description || '',
      relatedSegment: item.relatedSegment,
      severity: item.severity,
    })),
    keyCompaniesSummary: (dto.keyCompaniesSummary || []).map((item) => ({
      code: item.code,
      name: item.name,
      chainPosition: item.chainPosition,
      score: item.score,
    })),
  }
}

export function mapChainVersionSummary(dto: ApiChainVersionSummary): ChainVersionSummary {
  return {
    id: dto.id,
    industry: dto.industry,
    versionNo: dto.versionNo,
    label: dto.label,
    status: dto.status,
    model: dto.model,
    nodeCount: dto.nodeCount,
    companyCount: dto.companyCount,
    createdBy: dto.createdBy,
    createdAt: dto.createdAt,
  }
}

export function mapChainVersionDetail(dto: ApiChainVersionDetail): ChainVersionDetail {
  return {
    version: mapChainVersionSummary(dto.version),
    result: dto.result ? mapChainAnalysisResult(dto.result) : null,
    errorMsg: dto.errorMsg,
  }
}

export function mapChainCompareResult(dto: ApiChainCompareResult): ChainCompareResult {
  return {
    baseVersion: mapChainVersionSummary(dto.baseVersion),
    targetVersion: mapChainVersionSummary(dto.targetVersion),
    addedNodes: dto.addedNodes,
    removedNodes: dto.removedNodes,
    addedCompanies: dto.addedCompanies.map((item) => ({
      code: item.code,
      name: item.name,
      nodeName: item.nodeName,
    })),
    removedCompanies: dto.removedCompanies.map((item) => ({
      code: item.code,
      name: item.name,
      nodeName: item.nodeName,
    })),
    metricChanges: dto.metricChanges.map((item) => ({
      nodeName: item.nodeName,
      field: item.field,
      baseValue: item.baseValue,
      targetValue: item.targetValue,
    })),
  }
}
