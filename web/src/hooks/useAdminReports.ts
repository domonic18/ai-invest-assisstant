import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  cleanupOldReports,
  createAdminReport,
  deleteAdminReport,
  fetchAdminReports,
  fetchReportStorageSummary,
  updateAdminReport,
  type AdminReportParams,
} from '@/api/adminReports'
import type {
  ApiAdminReportCreateRequest,
  ApiAdminReportUpdateRequest,
} from '@ai-invest/shared'

import { queryKeys } from '@/hooks/queryKeys'

const ADMIN_REPORTS_KEY = queryKeys.admin.reports

export function useAdminReports(params: AdminReportParams = {}) {
  return useQuery({
    queryKey: [...ADMIN_REPORTS_KEY, params],
    queryFn: () => fetchAdminReports(params),
  })
}

export function useReportStorageSummary() {
  return useQuery({
    queryKey: [...ADMIN_REPORTS_KEY, 'storage-summary'],
    queryFn: fetchReportStorageSummary,
    staleTime: 60_000,
  })
}

export function useCreateAdminReport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ApiAdminReportCreateRequest) => createAdminReport(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ADMIN_REPORTS_KEY }),
  })
}

export function useUpdateAdminReport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiAdminReportUpdateRequest }) => updateAdminReport(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ADMIN_REPORTS_KEY }),
  })
}

export function useDeleteAdminReport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteAdminReport(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ADMIN_REPORTS_KEY }),
  })
}

export function useCleanupOldReports() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: cleanupOldReports,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ADMIN_REPORTS_KEY }),
  })
}
