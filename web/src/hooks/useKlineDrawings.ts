/**
 * 画线数据 hooks（F-DRAW）：一次拉取全周期 user+ai，周期切换前端过滤；
 * 写操作乐观更新 + 失败回滚 toast（arch/09 §3.3）。
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { message } from 'antd'
import type {
  AiKlineDrawingGroup,
  KlineDrawingTargetType,
  UserKlineDrawing,
  UserKlineDrawingCreateRequest,
  UserKlineDrawingUpdateRequest,
} from '@ai-invest/shared'

import {
  adoptAiDrawing,
  clearAiDrawings,
  createKlineDrawing,
  deleteAiDrawingItem,
  deleteKlineDrawing,
  fetchKlineDrawings,
  updateAiDrawingItem,
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
    get: () => queryClient.getQueryData(key),
    patchUser: (fn: (list: UserKlineDrawing[]) => UserKlineDrawing[]) => {
      const prev = queryClient.getQueryData(key)
      queryClient.setQueryData(key, (old: { user: UserKlineDrawing[]; ai: unknown[] } | undefined) =>
        old ? { ...old, user: fn(old.user) } : old,
      )
      return prev
    },
    patchAi: (fn: (groups: AiKlineDrawingGroup[]) => AiKlineDrawingGroup[]) => {
      const prev = queryClient.getQueryData(key)
      queryClient.setQueryData(
        key,
        (old: { user: UserKlineDrawing[]; ai: AiKlineDrawingGroup[] } | undefined) =>
          old ? { ...old, ai: fn(old.ai) } : old,
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

interface AiItemScope {
  period: 'daily' | 'weekly' | 'monthly'
  label: string
}

/** AI 组乐观更新定位器：按 period + label 找到组内单条（找不到返回原数组） */
function patchAiGroups(
  groups: AiKlineDrawingGroup[],
  scope: AiItemScope,
  patchItem: (item: AiKlineDrawingGroup['drawings'][number]) => AiKlineDrawingGroup['drawings'][number],
  remove = false,
): AiKlineDrawingGroup[] {
  return groups.map((group) => {
    if (group.period !== scope.period) return group
    const drawings = remove
      ? group.drawings.filter((item) => item.label !== scope.label)
      : group.drawings.map((item) => (item.label === scope.label ? patchItem(item) : item))
    return { ...group, drawings }
  })
}

/** AI 画线单条原位编辑（拖拽锚点 / 双击改名），乐观更新 AI 组避免拖拽回闪 */
export function useUpdateAiDrawingItem(targetType: KlineDrawingTargetType, targetCode: string) {
  const cache = useDrawingCache(targetType, targetCode)
  return useMutation({
    mutationFn: (payload: Parameters<typeof updateAiDrawingItem>[0]) => updateAiDrawingItem(payload),
    onMutate: async ({ period, label, anchors, newLabel }) => {
      await cache.cancel()
      const prev = cache.get()
      cache.patchAi((groups) =>
        patchAiGroups(groups, { period, label }, (item) => ({
          ...item,
          ...(anchors ? { anchors } : {}),
          ...(newLabel ? { label: newLabel } : {}),
        })),
      )
      return { prev } satisfies MutationCtx
    },
    onError: (err, _vars, ctx) => {
      if (ctx) cache.rollback(ctx.prev)
      message.error(`AI 画线更新失败：${(err as Error).message}`)
    },
  })
}

/** AI 画线单条删除（Delete 键） */
export function useDeleteAiDrawingItem(targetType: KlineDrawingTargetType, targetCode: string) {
  const cache = useDrawingCache(targetType, targetCode)
  return useMutation({
    mutationFn: (payload: Parameters<typeof deleteAiDrawingItem>[0]) => deleteAiDrawingItem(payload),
    onMutate: async ({ period, label }) => {
      await cache.cancel()
      const prev = cache.get()
      cache.patchAi((groups) => patchAiGroups(groups, { period, label }, (item) => item, true))
      return { prev } satisfies MutationCtx
    },
    onError: (err, _vars, ctx) => {
      if (ctx) cache.rollback(ctx.prev)
      message.error(`AI 画线删除失败：${(err as Error).message}`)
    },
  })
}

/** 清空指定周期的 AI 画线集 */
export function useClearAiDrawings(targetType: KlineDrawingTargetType, targetCode: string) {
  const cache = useDrawingCache(targetType, targetCode)
  return useMutation({
    mutationFn: (payload: Parameters<typeof clearAiDrawings>[0]) => clearAiDrawings(payload),
    onMutate: async ({ period }) => {
      await cache.cancel()
      const prev = cache.get()
      cache.patchAi((groups) => groups.filter((group) => group.period !== period))
      return { prev } satisfies MutationCtx
    },
    onError: (err, _vars, ctx) => {
      if (ctx) cache.rollback(ctx.prev)
      message.error(`AI 画线清除失败：${(err as Error).message}`)
    },
  })
}
