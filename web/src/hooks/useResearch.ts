import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  fetchResearchFilters,
  fetchResearchPdfUrl,
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

export function useResearchFilters() {
  return useQuery({
    queryKey: [...RESEARCH_KEY, 'filters'],
    queryFn: fetchResearchFilters,
    staleTime: 5 * 60 * 1000,
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
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number | string) => summarizeResearchReport(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: RESEARCH_KEY })
    },
  })
}

export function useResearchPdfUrl() {
  return useMutation({
    mutationFn: (id: number | string) => fetchResearchPdfUrl(id),
  })
}
