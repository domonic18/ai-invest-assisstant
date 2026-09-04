import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  analyzeChain,
  deleteChainVersion,
  fetchChainAlerts,
  fetchChainCompare,
  fetchChainIndustries,
  fetchChainLatest,
  fetchChainVersion,
  fetchChainVersions,
} from '@/api/chain'

export function useChainAlerts(industry: string | undefined, days = 30) {
  return useQuery({
    queryKey: ['chain', 'alerts', industry, days],
    queryFn: () => fetchChainAlerts(industry!, days),
    enabled: !!industry,
    staleTime: 5 * 60 * 1000,
  })
}

export function useChainLatest(industry: string | undefined) {
  return useQuery({
    queryKey: ['chain', 'latest', industry],
    queryFn: () => fetchChainLatest(industry!),
    enabled: !!industry,
    staleTime: 10 * 60 * 1000,
    retry: false,
  })
}

export function useChainIndustries() {
  return useQuery({
    queryKey: ['chain', 'industries'],
    queryFn: fetchChainIndustries,
    staleTime: 1 * 60 * 1000,
  })
}

export function useChainVersions(industry: string | undefined) {
  return useQuery({
    queryKey: ['chain', 'versions', industry],
    queryFn: () => fetchChainVersions(industry!),
    enabled: !!industry,
    staleTime: 10 * 60 * 1000,
  })
}

export function useChainVersion(versionId: number | null) {
  return useQuery({
    queryKey: ['chain', 'version', versionId],
    queryFn: () => fetchChainVersion(versionId!),
    enabled: versionId !== null,
    staleTime: Infinity,
  })
}

export function useChainCompare(baseId: number | null, targetId: number | null) {
  return useQuery({
    queryKey: ['chain', 'compare', baseId, targetId],
    queryFn: () => fetchChainCompare(baseId!, targetId!),
    enabled: baseId !== null && targetId !== null,
    staleTime: Infinity,
  })
}

export function useDeleteChainVersion() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteChainVersion,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chain'] })
    },
  })
}

export function useChainAnalysis(industry: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: analyzeChain,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chain', 'latest', industry] })
      queryClient.invalidateQueries({ queryKey: ['chain', 'versions', industry] })
    },
  })
}
