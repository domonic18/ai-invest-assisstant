export const REPORT_TYPE_OPTIONS = [
  { value: 'annual', label: '年报' },
  { value: 'semi_annual', label: '半年报' },
  { value: 'q1', label: '一季报' },
  { value: 'q3', label: '三季报' },
]

export const REPORT_TYPE_LABELS = new Map(
  REPORT_TYPE_OPTIONS.map((option) => [option.value, option.label]),
)

/** 类型 tag 配色对齐原型：年报紫 / 半年报蓝。 */
export const REPORT_TYPE_TAG_COLORS: Record<string, string> = {
  annual: 'purple',
  semi_annual: 'blue',
  q1: 'cyan',
  q3: 'geekblue',
}

export interface FinancialReportParams {
  q: string
  reportType?: string
  startDate?: string
  endDate?: string
  page: number
  pageSize: number
}

export interface SummaryPanel {
  reportId: number
  title: string
  content: string
  /** true 命中缓存（来自库内摘要）/ false 本次新生成 / null 未知。 */
  cached: boolean | null
}

export function formatFileSize(size: number | null): string | null {
  if (size == null) return null
  if (size >= 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`
  if (size >= 1024) return `${(size / 1024).toFixed(0)} KB`
  return `${size} B`
}
