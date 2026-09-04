import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { ApiFinancialReportCollectRequest } from '@ai-invest/shared'

import {
  collectFinancialReport,
  fetchFinancialReportCollectLog,
  fetchFinancialReportPdfUrl,
  fetchFinancialReports,
  summarizeFinancialReport,
  type FinancialReportParams,
} from '@/api/financial_report'

const FINANCIAL_REPORT_KEY = ['financial-reports'] as const
const IN_FLIGHT_STATUSES = new Set(['pending', 'running'])

export function useFinancialReports(params: FinancialReportParams = {}) {
  return useQuery({
    queryKey: [...FINANCIAL_REPORT_KEY, params],
    queryFn: () => fetchFinancialReports(params),
  })
}

export function useSummarizeFinancialReport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number | string) => summarizeFinancialReport(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: FINANCIAL_REPORT_KEY })
    },
  })
}

export function useFinancialReportPdfUrl() {
  return useMutation({
    mutationFn: (id: number | string) => fetchFinancialReportPdfUrl(id),
  })
}

export function useCollectFinancialReport() {
  return useMutation({
    mutationFn: (body: ApiFinancialReportCollectRequest) =>
      collectFinancialReport(body),
  })
}

export function useFinancialReportCollectLog(logId: number | null) {
  return useQuery({
    queryKey: [...FINANCIAL_REPORT_KEY, 'collect-log', logId],
    queryFn: () => fetchFinancialReportCollectLog(logId!),
    enabled: logId != null,
    refetchInterval: (query) =>
      query.state.data && IN_FLIGHT_STATUSES.has(query.state.data.status)
        ? 3000
        : false,
  })
}
