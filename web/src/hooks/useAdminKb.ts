import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  confirmKbCost,
  confirmKbMediaUploaded,
  createKbSource,
  deleteKbMedia,
  deleteKbSource,
  estimateKbCost,
  fetchKbSourceMedia,
  fetchKbSources,
  fetchKbTranscript,
  initKbMediaUploads,
  patchKbMedia,
  requeueKbMedia,
  restoreKbSource,
  saveKbTranscript,
  updateKbSource,
} from '@/api/adminKb'
import { fetchKbSettings, updateKbSettings } from '@/api/adminKb'
import type {
  ApiKbConfirmCostRequest,
  ApiKbCostEstimateRequest,
  ApiKbMediaInitRequest,
  ApiKbMediaPatchRequest,
  ApiKbProcessStatus,
  ApiKbSettingsUpdateRequest,
  ApiKbSourceCreateRequest,
  ApiKbSourceUpdateRequest,
  ApiKbTranscriptUpdateRequest,
} from '@ai-invest/shared'

import { queryKeys } from '@/hooks/queryKeys'

export function useKbSettings() {
  return useQuery({
    queryKey: queryKeys.kb.settings,
    queryFn: fetchKbSettings,
  })
}

export function useUpdateKbSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ApiKbSettingsUpdateRequest) => updateKbSettings(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.kb.settings }),
  })
}

export function useKbSources() {
  return useQuery({
    queryKey: queryKeys.kb.sources,
    queryFn: fetchKbSources,
  })
}

export function useCreateKbSource() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ApiKbSourceCreateRequest) => createKbSource(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.kb.sources }),
  })
}

export function useUpdateKbSource() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiKbSourceUpdateRequest }) =>
      updateKbSource(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.kb.sources }),
  })
}

export function useDeleteKbSource() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteKbSource(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.kb.sources }),
  })
}

export function useRestoreKbSource() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => restoreKbSource(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.kb.sources }),
  })
}

/** 进行中的状态需要轮询观察流转（queued→processing→done/failed）。 */
const MEDIA_ACTIVE_STATUSES: ApiKbProcessStatus[] = ['queued', 'processing']

export function useKbSourceMedia(sourceId: number | null) {
  return useQuery({
    queryKey: queryKeys.kb.media(sourceId ?? 0),
    queryFn: () => fetchKbSourceMedia(sourceId as number),
    enabled: sourceId != null,
    refetchInterval: (query) =>
      query.state.data?.some((m) => MEDIA_ACTIVE_STATUSES.includes(m.processStatus))
        ? 5_000
        : false,
  })
}

export function useInitKbMediaUploads() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ sourceId, data }: { sourceId: number; data: ApiKbMediaInitRequest }) =>
      initKbMediaUploads(sourceId, data),
    onSuccess: (_res, vars) =>
      queryClient.invalidateQueries({ queryKey: queryKeys.kb.media(vars.sourceId) }),
  })
}

export function useConfirmKbMediaUploaded() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (mediaId: number) => confirmKbMediaUploaded(mediaId),
    onSuccess: (media) =>
      queryClient.invalidateQueries({ queryKey: queryKeys.kb.media(media.sourceId) }),
  })
}

export function usePatchKbMedia() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ mediaId, data }: { mediaId: number; data: ApiKbMediaPatchRequest }) =>
      patchKbMedia(mediaId, data),
    onSuccess: (media) =>
      queryClient.invalidateQueries({ queryKey: queryKeys.kb.media(media.sourceId) }),
  })
}

export function useDeleteKbMedia() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (mediaId: number) => deleteKbMedia(mediaId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.kb.all }),
  })
}

export function useRequeueKbMedia() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (mediaId: number) => requeueKbMedia(mediaId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.kb.all }),
  })
}

export function useEstimateKbCost() {
  return useMutation({
    mutationFn: (data: ApiKbCostEstimateRequest) => estimateKbCost(data),
  })
}

export function useConfirmKbCost() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      sourceId,
      data,
    }: {
      sourceId: number
      data: ApiKbConfirmCostRequest
    }) => confirmKbCost(sourceId, data),
    onSuccess: (_res, vars) =>
      queryClient.invalidateQueries({ queryKey: queryKeys.kb.media(vars.sourceId) }),
  })
}

export function useKbTranscript(sourceId: number | null, mediaId: number | null) {
  return useQuery({
    queryKey: queryKeys.kb.transcript(sourceId ?? 0, mediaId ?? 0),
    queryFn: () => fetchKbTranscript(sourceId as number, mediaId as number),
    enabled: sourceId != null && mediaId != null,
  })
}

export function useSaveKbTranscript(sourceId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      mediaId,
      data,
    }: {
      mediaId: number
      data: ApiKbTranscriptUpdateRequest
    }) => saveKbTranscript(sourceId, mediaId, data),
    onSuccess: (_res, vars) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.kb.transcript(sourceId, vars.mediaId),
      })
      queryClient.invalidateQueries({ queryKey: queryKeys.kb.media(sourceId) })
    },
  })
}
