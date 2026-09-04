export const REPORT_TYPE_OPTIONS = [
  { value: 'annual', label: '年报' },
  { value: 'semi_annual', label: '半年报' },
  { value: 'q1', label: '一季报' },
  { value: 'q3', label: '三季报' },
]

export const REPORT_TYPE_LABELS = new Map(
  REPORT_TYPE_OPTIONS.map((option) => [option.value, option.label]),
)

export interface FinancialReportParams {
  q: string
  reportType?: string
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

export function formatFileSize(size: number | null): string | null {
  if (size == null) return null
  if (size >= 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`
  if (size >= 1024) return `${(size / 1024).toFixed(0)} KB`
  return `${size} B`
}
