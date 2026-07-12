export interface ChainNode {
  name: string
  type: 'upstream' | 'midstream' | 'downstream'
  companies: Array<{ code: string; name: string }>
  avgGrossMargin: number
  revenueGrowth: number
  bargainingPower: number
}

export interface ChainEdge {
  source: string
  target: string
  relation: string
  strength: number
  description: string
}

export interface ChainAnalysisResult {
  nodes: ChainNode[]
  edges: ChainEdge[]
  summary: string
  opportunities: string[]
  risks: string[]
}
