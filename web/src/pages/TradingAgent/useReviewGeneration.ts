/**
 * 复盘按需生成状态机：派发任务 → 轮询采集日志 → 终态刷新缓存并提示。
 *
 * agentKey 切换由调用方 ``key={agentKey}`` 重挂载复位，避免跨 Agent 的
 * pending 任务把新 Agent 面板卡在「生成中」。
 */

import { message } from 'antd'
import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import type {
  TradingAgentReviewGenerateRequest,
  TradingAgentReviewWindow,
} from '@ai-invest/shared'

import { queryKeys } from '@/hooks/queryKeys'
import {
  isReviewSuccessStatus,
  isReviewTerminalStatus,
  useGenerateTradingAgentReview,
  useReviewGenerationStatus,
} from '@/hooks/useTradingAgent'

/** 生成任务兜底超时：任务丢失时不无限轮询保持「生成中」。 */
export const REVIEW_GENERATION_TIMEOUT_MS = 15 * 60 * 1000

export interface ReviewGenerationState {
  generating: boolean
  runGenerate: () => void
}

export function useReviewGeneration(
  agentKey: string,
  window: TradingAgentReviewWindow,
  hasReview: boolean,
): ReviewGenerationState {
  const queryClient = useQueryClient()
  const [pendingLogId, setPendingLogId] = useState<number | null>(null)
  const generationStartedAt = useRef<number | null>(null)
  const generate = useGenerateTradingAgentReview(agentKey)
  const generationQuery = useReviewGenerationStatus(pendingLogId)

  useEffect(() => {
    if (pendingLogId === null) return
    const startedAt = generationStartedAt.current
    if (startedAt !== null && Date.now() - startedAt > REVIEW_GENERATION_TIMEOUT_MS) {
      generationStartedAt.current = null
      setPendingLogId(null)
      message.warning('复盘生成任务长时间未返回，请稍后刷新查看')
      return
    }
    const status = generationQuery.data?.collector_status
    if (!isReviewTerminalStatus(status)) return
    generationStartedAt.current = null
    setPendingLogId(null)
    if (isReviewSuccessStatus(status)) {
      message.success('复盘已生成')
      void queryClient.invalidateQueries({
        queryKey: queryKeys.tradingAgent.reviewAll(agentKey),
      })
      void queryClient.invalidateQueries({ queryKey: queryKeys.tradingAgent.dates(agentKey) })
    } else if (status === 'skipped') {
      message.info('生成任务被跳过（可能已有进行中的生成），请稍后刷新')
    } else {
      message.error('复盘生成失败，请稍后重试或查看采集日志')
    }
  }, [generationQuery, pendingLogId, agentKey, queryClient])

  const runGenerate = () => {
    const request: TradingAgentReviewGenerateRequest = {
      ...window,
      regenerate: hasReview,
    }
    generate.mutate(request, {
      onSuccess: (data) => {
        generationStartedAt.current = Date.now()
        setPendingLogId(data.logId)
        message.info('已派发复盘生成任务，完成后自动刷新')
      },
    })
  }

  return {
    generating: generate.isPending || pendingLogId !== null,
    runGenerate,
  }
}
