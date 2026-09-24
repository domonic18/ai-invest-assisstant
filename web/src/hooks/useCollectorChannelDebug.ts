import { useMutation } from '@tanstack/react-query'

import { debugCollectorChannel } from '@/api/collectorChannelDebug'
import type { CollectorChannelDebugRequest } from '@ai-invest/shared'

export function useCollectorChannelDebug() {
  return useMutation({
    mutationFn: ({
      channelId,
      request,
    }: {
      channelId: number
      request: CollectorChannelDebugRequest
    }) => debugCollectorChannel(channelId, request),
  })
}
