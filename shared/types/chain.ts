export interface ChainCompany {
  code: string
  name: string
}

export interface ChainNode {
  name: string
  type: 'upstream' | 'midstream' | 'downstream'
  description: string
  companies: ChainCompany[]
  avgGrossMargin: number | null
  revenueGrowth: number | null
  rdRatio: number | null
  bargainingPower: number | null
  localizationRate: number | null
  techBarrier: string | null
  bottleneckIndicators: string[]
  recentBreakthroughs: string[]
}

export interface ChainEdge {
  source: string
  target: string
  relation: string
  strength: number
  description: string
  criticality: string | null
}

export interface ChainOpportunity {
  title: string
  description: string
  relatedSegment: string | null
  confidence: string | null
}

export interface ChainRisk {
  title: string
  description: string
  relatedSegment: string | null
  severity: string | null
}

export interface ChainValueDistribution {
  highestMarginSegment: string | null
  highestMarginValue: number | null
  lowestMarginSegment: string | null
  lowestMarginValue: number | null
}

export interface KeyCompanySummary {
  code: string
  name: string
  chainPosition: string | null
  score: number | null
}

export interface ChainAnalysisResult {
  nodes: ChainNode[]
  edges: ChainEdge[]
  summary: string
  valueDistribution: ChainValueDistribution | null
  opportunities: ChainOpportunity[]
  risks: ChainRisk[]
  keyCompaniesSummary: KeyCompanySummary[]
}

export interface ChainVersionSummary {
  id: number
  industry: string
  versionNo: number
  label: string | null
  status: string
  model: string | null
  nodeCount: number | null
  companyCount: number | null
  createdBy: string
  createdAt: string
}

export interface ChainVersionDetail {
  version: ChainVersionSummary
  result: ChainAnalysisResult | null
  errorMsg: string | null
}

export interface ChainCompareCompanyChange {
  code: string
  name: string
  nodeName: string
}

export interface ChainCompareMetricChange {
  nodeName: string
  field: string
  baseValue: number | null
  targetValue: number | null
}

export interface ChainCompareResult {
  baseVersion: ChainVersionSummary
  targetVersion: ChainVersionSummary
  addedNodes: string[]
  removedNodes: string[]
  addedCompanies: ChainCompareCompanyChange[]
  removedCompanies: ChainCompareCompanyChange[]
  metricChanges: ChainCompareMetricChange[]
}

/** 产业链提醒类型：与后端 ChainAlertType 枚举一致。 */
export type ChainAlertType =
  | '财报异动'
  | '评级调整'
  | '技术突破'
  | '格局变化'
  | '政策催化'

/** 产业链提醒关联标的。 */
export interface ChainAlertStockRef {
  code: string
  name: string
  changePct: number | null
}

/** 产业链提醒（客户端视图模型）。 */
export interface ChainAlert {
  industry: string
  alertType: ChainAlertType
  severity: number
  title: string
  description: string
  affectedSegments: string[]
  relatedStocks: ChainAlertStockRef[]
  signalDate: string
  createdAt: string
}

export interface ApiChainAnalysisRequest {
  industry: string
  focus?: string | null
}

export interface ApiChainCompany {
  code: string
  name: string
}

export interface ApiChainNode {
  name: string
  type: 'upstream' | 'midstream' | 'downstream'
  description: string
  companies: ApiChainCompany[]
  avgGrossMargin: number | null
  revenueGrowth: number | null
  rdRatio: number | null
  bargainingPower: number | null
  localizationRate: number | null
  techBarrier: string | null
  bottleneckIndicators: string[]
  recentBreakthroughs: string[]
}

export interface ApiChainEdge {
  source: string
  target: string
  relation: string
  strength: number
  description?: string
  criticality: string | null
}

export interface ApiChainOpportunity {
  title: string
  description: string
  relatedSegment: string | null
  confidence: string | null
}

export interface ApiChainRisk {
  title: string
  description: string
  relatedSegment: string | null
  severity: string | null
}

export interface ApiChainValueDistribution {
  highestMarginSegment: string | null
  highestMarginValue: number | null
  lowestMarginSegment: string | null
  lowestMarginValue: number | null
}

export interface ApiKeyCompanySummary {
  code: string
  name: string
  chainPosition: string | null
  score: number | null
}

export interface ApiChainAnalysisResult {
  nodes: ApiChainNode[]
  edges: ApiChainEdge[]
  summary: string
  valueDistribution: ApiChainValueDistribution | null
  opportunities: ApiChainOpportunity[]
  risks: ApiChainRisk[]
  keyCompaniesSummary: ApiKeyCompanySummary[]
}

export interface ApiChainAnalyzeResponse {
  versionId: number
  versionNo: number
  status: string
  result: ApiChainAnalysisResult | null
}

export interface ApiChainVersionSummary {
  id: number
  industry: string
  versionNo: number
  label: string | null
  status: string
  model: string | null
  nodeCount: number | null
  companyCount: number | null
  createdBy: string
  createdAt: string
}

export interface ApiChainVersionDetail {
  version: ApiChainVersionSummary
  result: ApiChainAnalysisResult | null
  errorMsg: string | null
}

export interface ApiChainCompareCompanyChange {
  code: string
  name: string
  nodeName: string
}

export interface ApiChainCompareMetricChange {
  nodeName: string
  field: string
  baseValue: number | null
  targetValue: number | null
}

export interface ApiChainCompareResult {
  baseVersion: ApiChainVersionSummary
  targetVersion: ApiChainVersionSummary
  addedNodes: string[]
  removedNodes: string[]
  addedCompanies: ApiChainCompareCompanyChange[]
  removedCompanies: ApiChainCompareCompanyChange[]
  metricChanges: ApiChainCompareMetricChange[]
}

/** 产业链提醒关联标的（名称 + 当日涨跌幅）。 */
export interface ApiChainAlertStockRef {
  code: string
  name: string
  changePct: number | null
}

export interface ApiChainAlert {
  industry: string
  alertType: string
  severity: number
  title: string
  description: string
  affectedSegments: string[]
  relatedStocks: ApiChainAlertStockRef[]
  signalDate: string
  createdAt: string
}
