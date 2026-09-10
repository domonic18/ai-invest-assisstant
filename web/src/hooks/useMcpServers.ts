import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createMcpServer,
  deleteMcpServer,
  fetchMcpServers,
  testMcpServer,
  testMcpServerDraft,
  updateMcpServer,
} from '@/api/adminMcpServers'
import type {
  ApiMcpServerCreateRequest,
  ApiMcpServerUpdateRequest,
} from '@ai-invest/shared'

import { queryKeys } from '@/hooks/queryKeys'

const MCP_SERVERS_KEY = queryKeys.mcpServers

export function useMcpServers() {
  return useQuery({
    queryKey: MCP_SERVERS_KEY,
    queryFn: fetchMcpServers,
  })
}

export function useCreateMcpServer() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ApiMcpServerCreateRequest) => createMcpServer(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: MCP_SERVERS_KEY }),
  })
}

export function useUpdateMcpServer() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiMcpServerUpdateRequest }) =>
      updateMcpServer(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: MCP_SERVERS_KEY }),
  })
}

export function useDeleteMcpServer() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteMcpServer(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: MCP_SERVERS_KEY }),
  })
}

export function useTestMcpServer() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => testMcpServer(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: MCP_SERVERS_KEY }),
  })
}

export function useTestMcpServerDraft() {
  return useMutation({
    mutationFn: (data: ApiMcpServerCreateRequest) => testMcpServerDraft(data),
  })
}
