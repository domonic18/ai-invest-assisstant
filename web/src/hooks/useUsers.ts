import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { message } from 'antd'
import type { ApiPasswordChangeRequest } from '@ai-invest/shared'

import { changeMyPassword, fetchMyProfile, updateMyEmail } from '@/api/users'
import { queryKeys } from '@/hooks/queryKeys'

export function useMyProfile() {
  return useQuery({
    queryKey: queryKeys.users.me,
    queryFn: fetchMyProfile,
    staleTime: 60_000,
  })
}

export function useUpdateMyEmail() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (email: string) => updateMyEmail(email),
    onSuccess: (user) => {
      message.success(`邮箱已更新为 ${user.email}`)
      void queryClient.invalidateQueries({ queryKey: queryKeys.users.all })
    },
    onError: (error: Error) => message.error(error.message),
  })
}

export function useChangeMyPassword() {
  return useMutation({
    mutationFn: (data: ApiPasswordChangeRequest) => changeMyPassword(data),
    onError: (error: Error) => message.error(error.message),
  })
}
