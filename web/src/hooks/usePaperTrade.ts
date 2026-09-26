import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { message } from 'antd'
import { useEffect, useRef } from 'react'

import {
  cancelPaperTradeOrder,
  clearPaperTradeAgentAccount,
  createPaperTradeAccount,
  deletePaperTradeAccount,
  designatePaperTradeAgentAccount,
  fetchAdminPaperTradeAccounts,
  fetchPaperTradeAccounts,
  fetchPaperTradeExecutions,
  fetchPaperTradeNav,
  fetchPaperTradeOrders,
  fetchPaperTradeOverview,
  fetchPaperTradeTradeMarkers,
  placePaperTradeOrder,
  setPaperTradeAccountEnabled,
  syncPaperTradeAccount,
  updatePaperTradeAccount,
} from '@/api/paperTrade'
import type {
  ApiPaperTradeAccountSaveRequest,
  ApiPaperTradePlaceOrderRequest,
} from '@ai-invest/shared'
import { queryKeys } from '@/hooks/queryKeys'

// ============================================================
// 错误提示
// ============================================================

/** 掘金柜台 401 经 sidecar/app 链路透传为 503 +「token 无效」文案（serverDetail 已被拦截器写入 message）。 */
export function isTokenInvalidError(error: unknown): boolean {
  return error instanceof Error && error.message.includes('token 无效')
}

/** 柜台报错统一弹窗（无全局 toast，逐 mutation 挂 onError）。 */
function notifyMutationError(error: Error) {
  message.error(error.message)
}


// ============================================================
// 账户配置
// ============================================================

export function usePaperTradeAccounts() {
  return useQuery({
    queryKey: queryKeys.paperTrade.accounts,
    queryFn: fetchPaperTradeAccounts,
  })
}

export function useSavePaperTradeAccount() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      accountId,
      data,
    }: {
      accountId?: number
      data: ApiPaperTradeAccountSaveRequest
    }) =>
      accountId == null
        ? createPaperTradeAccount(data)
        : updatePaperTradeAccount(accountId, data),
    onSuccess: (_account, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.paperTrade.accounts })
      message.success(variables.accountId == null ? '账户已添加' : '账户已更新')
    },
    onError: notifyMutationError,
  })
}

export function useDeletePaperTradeAccount() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (accountId: number) => deletePaperTradeAccount(accountId),
    onSuccess: () => {
      // 删除可能因数据守卫失败（409 弹窗见 onError），成功时连页面数据一起失效
      void queryClient.invalidateQueries({ queryKey: queryKeys.paperTrade.all })
    },
    onError: notifyMutationError,
  })
}

// ============================================================
// 管理端（列表 / 指定 agent / 启停）
// ============================================================

export function useAdminPaperTradeAccounts() {
  return useQuery({
    queryKey: queryKeys.paperTrade.adminAccounts,
    queryFn: fetchAdminPaperTradeAccounts,
  })
}

export function useDesignatePaperTradeAgent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (accountId: number) => designatePaperTradeAgentAccount(accountId),
    onSuccess: (account) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.paperTrade.all })
      message.success(`「${account.name}」已设为 agent 专属账户（全局唯一，原 agent 已还原）`)
    },
  })
}

export function useClearPaperTradeAgent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (accountId: number) => clearPaperTradeAgentAccount(accountId),
    onSuccess: (account) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.paperTrade.all })
      message.success(`「${account.name}」已取消 agent 关联（可随时重新指定）`)
    },
  })
}

export function useSetPaperTradeAccountEnabled() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ accountId, enabled }: { accountId: number; enabled: boolean }) =>
      setPaperTradeAccountEnabled(accountId, enabled),
    onSuccess: (account, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.paperTrade.all })
      message.success(
        `「${account.name}」已${variables.enabled ? '启用' : '停用'}（停用后跳过盘后同步并禁止人工交易）`,
      )
    },
  })
}

// ============================================================
// 行情与交易查询（恒按账户）
// ============================================================

export function usePaperTradeOverview(accountId?: number) {
  return useQuery({
    queryKey: queryKeys.paperTrade.overview(accountId),
    queryFn: () => fetchPaperTradeOverview(accountId as number),
    enabled: accountId != null,
  })
}

export function usePaperTradeOrders(
  accountId: number | undefined,
  tradeDate?: string,
  page = 1,
  pageSize = 20,
  refetchInterval?: number | false | (() => number | false | undefined),
) {
  return useQuery({
    queryKey: queryKeys.paperTrade.orders(accountId, tradeDate, page, pageSize),
    queryFn: () =>
      fetchPaperTradeOrders({
        accountId: accountId as number,
        tradeDate,
        page,
        pageSize,
      }),
    enabled: accountId != null,
    refetchInterval,
  })
}

export function usePaperTradeExecutions(
  accountId: number | undefined,
  tradeDate?: string,
  page = 1,
  pageSize = 20,
) {
  return useQuery({
    queryKey: queryKeys.paperTrade.executions(accountId, tradeDate, page, pageSize),
    queryFn: () =>
      fetchPaperTradeExecutions({
        accountId: accountId as number,
        tradeDate,
        page,
        pageSize,
      }),
    enabled: accountId != null,
  })
}

export function usePaperTradeNav(accountId: number | undefined, days = 30) {
  return useQuery({
    queryKey: queryKeys.paperTrade.nav(accountId, days),
    queryFn: () => fetchPaperTradeNav(accountId as number, days),
    enabled: accountId != null,
  })
}

/** B/S/T 图表标记：当前用户全账户对该标的的成交回报（个股详情页消费）。 */
export function usePaperTradeTradeMarkers(stockCode: string | undefined, days = 120) {
  return useQuery({
    queryKey: queryKeys.paperTrade.tradeMarkers(stockCode, days),
    queryFn: () => fetchPaperTradeTradeMarkers(stockCode as string, days),
    enabled: !!stockCode && /^\d{6}$/.test(stockCode),
    staleTime: 5 * 60_000,
  })
}

// ============================================================
// 人工交易（agent 专属账户 403）
// ============================================================

export function usePlacePaperTradeOrder() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ApiPaperTradePlaceOrderRequest) => placePaperTradeOrder(data),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.paperTrade.all })
      message.success(
        result.clOrdId ? `委托已提交（${result.clOrdId}）` : '委托已提交',
      )
    },
    onError: notifyMutationError,
  })
}

export function useCancelPaperTradeOrder() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ accountId, clOrdId }: { accountId: number; clOrdId: string }) =>
      cancelPaperTradeOrder(accountId, clOrdId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.paperTrade.all })
      message.success('撤单已提交')
    },
    onError: notifyMutationError,
  })
}

/** 单账户即时同步：下单/撤单后让委托成交历史立即反映柜台状态（带成功提示）。 */
export function useSyncPaperTradeAccount() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (accountId: number) => syncPaperTradeAccount(accountId),
    onSuccess: (summary) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.paperTrade.all })
      message.success(`同步完成（委托 ${summary.orders} 笔 / 成交 ${summary.executions} 笔）`)
    },
    onError: notifyMutationError,
  })
}

/** 静默同步：只失效查询不弹提示（委托状态自动推进的 t+3s/t+15s 补同步）。 */
export function useSilentPaperTradeSync() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (accountId: number) => syncPaperTradeAccount(accountId),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.paperTrade.all })
    },
  })
}

/** 延迟静默补同步：下单/撤单后在 t+3s 与 t+15s 各补一次（柜台回报异步到达）。 */
export function useDelayedPaperTradeSync() {
  const silentSync = useSilentPaperTradeSync()
  const timers = useRef<ReturnType<typeof setTimeout>[]>([])

  useEffect(
    () => () => {
      for (const timer of timers.current) clearTimeout(timer)
    },
    [],
  )

  return (accountId: number) => {
    for (const delayMs of [3000, 15000]) {
      timers.current.push(
        setTimeout(() => silentSync.mutate(accountId), delayMs),
      )
    }
  }
}

/** 即时同步柜台动作（带成功提示）；工具栏按钮与撤单后即时刷新共用同一实例。 */
export function usePaperTradeSyncAction() {
  const syncMutation = useSyncPaperTradeAccount()
  const syncRun = async (accountId: number) => {
    try {
      await syncMutation.mutateAsync(accountId)
    } catch {
      // 同步失败（锁冲突/柜台不可达）由全局拦截器提示
    }
  }
  return { syncRun, pending: syncMutation.isPending }
}
