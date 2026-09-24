import { useQueryClient } from '@tanstack/react-query'
import { message } from 'antd'
import { useEffect, useState } from 'react'

import type { PageEventType } from '@ai-invest/shared'

import { queryKeys } from '@/hooks/queryKeys'
import { usePageAssistantResult } from '@/hooks/usePageAssistantResult'
import { useAssistantStore } from '@/stores/assistant'

/**
 * 异动页 AI 归因触发的公共状态：订阅归因完成事件刷新榜单，
 * 侧边栏关闭（含 agent 中途被放弃）时复位进行中态。
 */
export function useAnomalyAttribution(eventType: PageEventType) {
  const queryClient = useQueryClient()
  const [generating, setGenerating] = useState(false)
  const panelOpen = useAssistantStore((s) => s.open)

  usePageAssistantResult(eventType, () => {
    setGenerating(false)
    void queryClient.invalidateQueries({ queryKey: queryKeys.anomaly.all })
    message.success('AI 归因已生成，榜单已刷新')
    return true
  })

  useEffect(() => {
    if (!panelOpen) setGenerating(false)
  }, [panelOpen])

  return generating
}
