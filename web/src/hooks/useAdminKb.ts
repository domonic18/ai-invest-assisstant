import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  approveKbPoint,
  approveKbPointsBatch,
  confirmKbCost,
  confirmKbMediaUploaded,
  createKbPoint,
  createKbSource,
  deleteKbMedia,
  deleteKbSource,
  estimateKbCost,
  fetchKbChapters,
  fetchKbImages,
  fetchKbReviewPoints,
  fetchKbSourceMedia,
  fetchKbSources,
  fetchKbTranscript,
  initKbMediaUploads,
  mergeKbPoints,
  patchKbImage,
  patchKbMedia,
  patchKbPoint,
  redescribeKbImage,
  rejectKbPoint,
  requeueKbMedia,
  restoreKbSource,
  saveKbTranscript,
  updateKbSource,
} from '@/api/adminKb'
import { fetchKbSettings, fetchKbUsage, publishKbChapters, updateKbSettings } from '@/api/adminKb'
import type {
  ApiKbChaptersPublishRequest,
  ApiKbConfirmCostRequest,
  ApiKbCostEstimateRequest,
  ApiKbImageExcludedRequest,
  ApiKbMediaInitRequest,
  ApiKbMediaPatchRequest,
  ApiKbPointCreateRequest,
  ApiKbPointPatchRequest,
  ApiKbPointRejectRequest,
  ApiKbPointsBatchApproveRequest,
  ApiKbPointsMergeRequest,
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

export function useKbUsage(
  sourceId: number | null,
  dateFrom: string | null,
  dateTo: string | null
) {
  return useQuery({
    queryKey: queryKeys.kb.usage(sourceId, dateFrom, dateTo),
    queryFn: () =>
      fetchKbUsage({
        sourceId: sourceId ?? undefined,
        dateFrom: dateFrom ?? undefined,
        dateTo: dateTo ?? undefined,
      }),
  })
}

export function useKbSources(enabled = true) {
  return useQuery({
    queryKey: queryKeys.kb.sources,
    queryFn: fetchKbSources,
    enabled,
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

// ---- 知识审核（F-KB-03）----

export function useKbChapters(sourceId: number | null) {
  return useQuery({
    queryKey: queryKeys.kb.chapters(sourceId ?? 0),
    queryFn: () => fetchKbChapters(sourceId as number),
    enabled: sourceId != null,
  })
}

export function usePublishKbChapters(sourceId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ApiKbChaptersPublishRequest) =>
      publishKbChapters(sourceId, data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: queryKeys.kb.chapters(sourceId) }),
  })
}

export function useKbReviewPoints(
  sourceId: number | null,
  status: string | null,
  page: number,
  pageSize: number
) {
  return useQuery({
    queryKey: queryKeys.kb.points(sourceId ?? 0, status, page, pageSize),
    queryFn: () =>
      fetchKbReviewPoints(sourceId as number, {
        status: status ?? undefined,
        page,
        pageSize,
      }),
    enabled: sourceId != null,
  })
}

function useInvalidateKbReview() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: queryKeys.kb.all })
}

export function useKbImages(
  sourceId: number | null,
  mediaId: number | null,
  status: string | null,
  page: number,
  pageSize: number
) {
  return useQuery({
    queryKey: queryKeys.kb.images(sourceId ?? 0, mediaId, status, page, pageSize),
    queryFn: () =>
      fetchKbImages(sourceId as number, {
        mediaId: mediaId ?? undefined,
        status: status ?? undefined,
        page,
        pageSize,
      }),
    enabled: sourceId != null,
  })
}

export function useRedescribeKbImage() {
  const invalidate = useInvalidateKbReview()
  return useMutation({
    mutationFn: (imageId: number) => redescribeKbImage(imageId),
    onSuccess: invalidate,
  })
}

export function usePatchKbImage() {
  const invalidate = useInvalidateKbReview()
  return useMutation({
    mutationFn: ({ imageId, data }: { imageId: number; data: ApiKbImageExcludedRequest }) =>
      patchKbImage(imageId, data),
    onSuccess: invalidate,
  })
}

export function useCreateKbPoint() {
  const invalidate = useInvalidateKbReview()
  return useMutation({
    mutationFn: (data: ApiKbPointCreateRequest) => createKbPoint(data),
    onSuccess: invalidate,
  })
}

export function usePatchKbPoint() {
  const invalidate = useInvalidateKbReview()
  return useMutation({
    mutationFn: ({ pointId, data }: { pointId: number; data: ApiKbPointPatchRequest }) =>
      patchKbPoint(pointId, data),
    onSuccess: invalidate,
  })
}

export function useApproveKbPoint() {
  const invalidate = useInvalidateKbReview()
  return useMutation({
    mutationFn: (pointId: number) => approveKbPoint(pointId),
    onSuccess: invalidate,
  })
}

export function useRejectKbPoint() {
  const invalidate = useInvalidateKbReview()
  return useMutation({
    mutationFn: ({ pointId, data }: { pointId: number; data: ApiKbPointRejectRequest }) =>
      rejectKbPoint(pointId, data),
    onSuccess: invalidate,
  })
}

export function useMergeKbPoints() {
  const invalidate = useInvalidateKbReview()
  return useMutation({
    mutationFn: (data: ApiKbPointsMergeRequest) => mergeKbPoints(data),
    onSuccess: invalidate,
  })
}

export function useApproveKbPointsBatch() {
  const invalidate = useInvalidateKbReview()
  return useMutation({
    mutationFn: (data: ApiKbPointsBatchApproveRequest) => approveKbPointsBatch(data),
    onSuccess: invalidate,
  })
}
