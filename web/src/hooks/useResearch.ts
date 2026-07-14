import { useMutation, useQuery } from '@tanstack/react-query'

import {
  fetchResearchReportDetail,
  fetchResearchReports,
  summarizeResearchReport,
  type ResearchParams,
} from '@/api/research'

const RESEARCH_KEY = ['research'] as const

export function useResearch(params: ResearchParams = {}) {
  return useQuery({
    queryKey: [...RESEARCH_KEY, params],
    queryFn: () => fetchResearchReports(params),
  })
}

export function useResearchReport(id: number | string | null) {
  return useQuery({
    queryKey: ['research-report', id],
    queryFn: () => fetchResearchReportDetail(id!),
    enabled: !!id,
  })
}

export function useSummarizeResearchReport() {
  return useMutation({
    mutationFn: (id: number | string) => summarizeResearchReport(id),
  })
}
