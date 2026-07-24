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
