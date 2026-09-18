import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { fetchKbSettings, updateKbSettings } from '@/api/adminKb'
import type { ApiKbSettingsUpdateRequest } from '@ai-invest/shared'

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
