export interface ResearchParams {
  q: string
  industry?: string
  broker?: string
  startDate?: string
  endDate?: string
  page: number
  pageSize: number
}

export interface SummaryModal {
  title: string
  content: string
}

export function summarySnippet(summary: string): string {
  return summary
    .replace(/[#*`>-]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}
