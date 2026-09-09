import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { message } from 'antd'
import type {
  ApiCustomSkillCreateRequest,
  ApiCustomSkillUpdateRequest,
} from '@ai-invest/shared'

import {
  createCustomSkill,
  fetchSkillDetail,
  fetchSkillFiles,
  fetchSkillSquare,
  installSkill,
  publishCustomSkill,
  uninstallSkill,
  updateCustomSkill,
} from '@/api/skills'
import { queryKeys } from '@/hooks/queryKeys'

export function useSkillSquare() {
  return useQuery({
    queryKey: queryKeys.skills.square,
    queryFn: fetchSkillSquare,
  })
}

export function useSkillDetail(skillId: string | null) {
  return useQuery({
    queryKey: queryKeys.skills.detail(skillId ?? ''),
    queryFn: () => fetchSkillDetail(skillId as string),
    enabled: skillId != null,
  })
}

export function useSkillFiles(skillId: string | null) {
  return useQuery({
    queryKey: queryKeys.skills.files(skillId ?? ''),
    queryFn: () => fetchSkillFiles(skillId as string),
    enabled: skillId != null,
  })
}

export function useInstallSkill() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (skillId: string) => installSkill(skillId),
    onSuccess: () => {
      message.success('技能已安装')
      void queryClient.invalidateQueries({ queryKey: queryKeys.skills.all })
    },
    onError: (error: Error) => message.error(error.message),
  })
}

export function useUninstallSkill() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (skillId: string) => uninstallSkill(skillId),
    onSuccess: () => {
      message.success('技能已卸载')
      void queryClient.invalidateQueries({ queryKey: queryKeys.skills.all })
    },
    onError: (error: Error) => message.error(error.message),
  })
}

export function useCreateCustomSkill() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: ApiCustomSkillCreateRequest) => createCustomSkill(payload),
    onSuccess: () => {
      message.success('自定义技能已创建（草稿）')
      void queryClient.invalidateQueries({ queryKey: queryKeys.skills.all })
    },
    onError: (error: Error) => message.error(error.message),
  })
}

export function useUpdateCustomSkill() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ skillId, payload }: { skillId: string; payload: ApiCustomSkillUpdateRequest }) =>
      updateCustomSkill(skillId, payload),
    onSuccess: () => {
      message.success('自定义技能已保存，版本 +1')
      void queryClient.invalidateQueries({ queryKey: queryKeys.skills.all })
    },
    onError: (error: Error) => message.error(error.message),
  })
}

export function usePublishCustomSkill() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (skillId: string) => publishCustomSkill(skillId),
    onSuccess: () => {
      message.success('技能已发布，广场可见')
      void queryClient.invalidateQueries({ queryKey: queryKeys.skills.all })
    },
    onError: (error: Error) => message.error(error.message),
  })
}
