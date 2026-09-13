/**
 * 画线数据 hooks（F-DRAW）：一次拉取全周期 user+ai，周期切换前端过滤；
 * 写操作乐观更新 + 失败回滚 toast（arch/09 §3.3）。
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { message } from 'antd'
import type {
  KlineDrawingTargetType,
  UserKlineDrawing,
  UserKlineDrawingCreateRequest,
  UserKlineDrawingUpdateRequest,
} from '@ai-invest/shared'

import {
  adoptAiDrawing,
  createKlineDrawing,
  deleteKlineDrawing,
  fetchKlineDrawings,
  updateKlineDrawing,
} from '@/api/drawings'
import { queryKeys } from './queryKeys'

export function useKlineDrawings(targetType: KlineDrawingTargetType, targetCode: string) {
  return useQuery({
    queryKey: queryKeys.klineDrawings.target(targetType, targetCode),
    queryFn: () => fetchKlineDrawings(targetType, targetCode),
    enabled: !!targetCode,
  })
}

interface MutationCtx {
  prev: unknown
  tempId?: string
}

function useDrawingCache(targetType: KlineDrawingTargetType, targetCode: string) {
  const queryClient = useQueryClient()
  const key = queryKeys.klineDrawings.target(targetType, targetCode)
  return {
    key,
    /** 乐观写前取消在途请求（避免旧响应覆盖乐观状态） */
    cancel: () => queryClient.cancelQueries({ queryKey: key }),
    /** 变更后整 key 失效（user/ai 两块都可能有变化） */
    invalidate: () => queryClient.invalidateQueries({ queryKey: key }),
    rollback: (prev: unknown) => queryClient.setQueryData(key, prev),
    patchUser: (fn: (list: UserKlineDrawing[]) => UserKlineDrawing[]) => {
      const prev = queryClient.getQueryData(key)
      queryClient.setQueryData(key, (old: { user: UserKlineDrawing[]; ai: unknown[] } | undefined) =>
        old ? { ...old, user: fn(old.user) } : old,
      )
      return prev
    },
  }
}

export function useCreateKlineDrawing(
  targetType: KlineDrawingTargetType,
  targetCode: string,
  onCreated?: (created: UserKlineDrawing) => void,
) {
  const cache = useDrawingCache(targetType, targetCode)
  return useMutation({
    mutationFn: (payload: UserKlineDrawingCreateRequest) => createKlineDrawing(payload),
    onMutate: async (payload) => {
      await cache.cancel()
      const tempId = `temp-${Date.now()}`
      const prev = cache.patchUser((list) => [
        ...list,
        { ...payload, id: tempId },
      ])
      return { prev, tempId } satisfies MutationCtx
    },
    onSuccess: (created, _payload, ctx) => {
      cache.patchUser((list) => list.map((d) => (d.id === ctx?.tempId ? created : d)))
      onCreated?.(created)
    },
    onError: (err, _payload, ctx) => {
      if (ctx) cache.rollback(ctx.prev)
      message.error(`画线保存失败：${(err as Error).message}`)
    },
  })
}

export function useUpdateKlineDrawing(targetType: KlineDrawingTargetType, targetCode: string) {
  const cache = useDrawingCache(targetType, targetCode)
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UserKlineDrawingUpdateRequest }) =>
      updateKlineDrawing(id, data),
    onMutate: async ({ id, data }) => {
      await cache.cancel()
      const prev = cache.patchUser((list) =>
        list.map((d) =>
          d.id === id
            ? {
                ...d,
                ...('anchors' in data && data.anchors != null ? { anchors: data.anchors } : {}),
                ...('direction' in data && data.direction != null ? { direction: data.direction } : {}),
                ...('style' in data && data.style != null ? { style: data.style } : {}),
                ...(data.text !== undefined ? { text: data.text ?? undefined } : {}),
              }
            : d,
        ),
      )
      return { prev } satisfies MutationCtx
    },
    onSuccess: (updated) => {
      cache.patchUser((list) => list.map((d) => (d.id === updated.id ? updated : d)))
    },
    onError: (err, _vars, ctx) => {
      if (ctx) cache.rollback(ctx.prev)
      message.error(`画线更新失败：${(err as Error).message}`)
    },
  })
}

export function useDeleteKlineDrawing(targetType: KlineDrawingTargetType, targetCode: string) {
  const cache = useDrawingCache(targetType, targetCode)
  return useMutation({
    mutationFn: (id: string) => deleteKlineDrawing(id),
    onMutate: async (id) => {
      await cache.cancel()
      const prev = cache.patchUser((list) => list.filter((d) => d.id !== id))
      return { prev } satisfies MutationCtx
    },
    onError: (err, _id, ctx) => {
      if (ctx) cache.rollback(ctx.prev)
      message.error(`画线删除失败：${(err as Error).message}`)
    },
  })
}

export function useAdoptAiDrawing(targetType: KlineDrawingTargetType, targetCode: string) {
  const cache = useDrawingCache(targetType, targetCode)
  return useMutation({
    mutationFn: (payload: Parameters<typeof adoptAiDrawing>[0]) => adoptAiDrawing(payload),
    onSuccess: (created) => {
      cache.patchUser((list) => [...list, created])
      cache.invalidate()
      message.success(`已采纳 AI 画线「${created.text ?? ''}」`)
    },
    onError: (err) => {
      message.error(`采纳失败：${(err as Error).message}`)
    },
  })
}
