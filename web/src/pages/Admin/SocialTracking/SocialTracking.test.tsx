import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type {
  ApiSocialAccountAdmin,
  ApiSocialAccountsAdminPage,
  ApiSocialStatus,
} from '@ai-invest/shared'

vi.mock('@/hooks/useAdminSocial', () => ({
  useSocialAccountsAdmin: vi.fn(),
  useSocialAccountPosts: vi.fn(),
  useSocialAdminStatus: vi.fn(),
  useAsrConfig: vi.fn(),
  useCreateSocialAccount: vi.fn(),
  useUpdateSocialAccount: vi.fn(),
  useDeleteSocialAccount: vi.fn(),
  useBackfillSocialAccount: vi.fn(),
  useImportSocialCookie: vi.fn(),
  useUpdateAsrConfig: vi.fn(),
  useTestAsrConfig: vi.fn(),
}))

import {
  useAsrConfig,
  useBackfillSocialAccount,
  useCreateSocialAccount,
  useDeleteSocialAccount,
  useImportSocialCookie,
  useSocialAccountPosts,
  useSocialAccountsAdmin,
  useSocialAdminStatus,
  useTestAsrConfig,
  useUpdateAsrConfig,
  useUpdateSocialAccount,
} from '@/hooks/useAdminSocial'

import { SocialTracking } from './SocialTracking'

const account: ApiSocialAccountAdmin = {
  id: 1,
  platform: 'douyin',
  secUid: 'MS4wLjABAAAA' + 'a'.repeat(20),
  alias: '财经大V-A',
  category: 'finance_kol',
  pollIntervalMinutes: 60,
  isActive: true,
  remark: null,
  lastCollectedAt: '2026-09-15T02:00:00Z',
  lastPostAt: '2026-09-15T01:30:00Z',
  lastError: null,
  lastErrorAt: null,
  createdAt: '2026-09-01T00:00:00Z',
}

const accountsPage: ApiSocialAccountsAdminPage = {
  items: [account],
  total: 1,
  page: 1,
  pageSize: 20,
}

const status: ApiSocialStatus = {
  douyin: {
    cookieConfigured: true,
    cookieJarsAvailable: 2,
    lastBootstrapAt: '2026-09-15T00:00:00Z',
    signatureWarning: false,
    todayCollected: 12,
    todayFailed: 1,
  },
  asr: {
    enabled: true,
    configured: true,
    todayTranscribed: 10,
    todayDegraded: 2,
  },
  signer: {
    enabled: true,
    reachable: true,
    warmSlots: 2,
    detail: null,
  },
}

function setupMocks(overrides: {
  updateMutate?: ReturnType<typeof vi.fn>
  deleteMutate?: ReturnType<typeof vi.fn>
  backfillMutate?: ReturnType<typeof vi.fn>
} = {}) {
  const mutate = vi.fn().mockResolvedValue(account)
  const mutateDelete = vi.fn().mockResolvedValue(undefined)
  const mutateBackfill = vi.fn().mockResolvedValue({ logId: 42, celeryTaskId: 'celery-abc' })
  const mutation = (fn: ReturnType<typeof vi.fn>) => ({
    isPending: false,
    mutateAsync: fn,
    variables: undefined,
  })
  vi.mocked(useSocialAccountsAdmin).mockReturnValue({
    data: accountsPage,
    isLoading: false,
  } as unknown as ReturnType<typeof useSocialAccountsAdmin>)
  vi.mocked(useSocialAdminStatus).mockReturnValue({
    data: status,
    isLoading: false,
  } as unknown as ReturnType<typeof useSocialAdminStatus>)
  vi.mocked(useAsrConfig).mockReturnValue({
    data: null,
    isLoading: false,
  } as unknown as ReturnType<typeof useAsrConfig>)
  vi.mocked(useCreateSocialAccount).mockReturnValue(
    mutation(vi.fn().mockResolvedValue(account)) as unknown as ReturnType<
      typeof useCreateSocialAccount
    >,
  )
  vi.mocked(useUpdateSocialAccount).mockReturnValue(
    mutation(overrides.updateMutate ?? mutate) as unknown as ReturnType<
      typeof useUpdateSocialAccount
    >,
  )
  vi.mocked(useDeleteSocialAccount).mockReturnValue(
    mutation(overrides.deleteMutate ?? mutateDelete) as unknown as ReturnType<
      typeof useDeleteSocialAccount
    >,
  )
  vi.mocked(useSocialAccountPosts).mockReturnValue({
    data: [
      {
        videoId: 'v001',
        title: '今日复盘',
        publishedAt: '2026-09-15T01:30:00Z',
        transcriptStatus: 'missing',
        transcriptReason: 'asr_disabled',
        judgedAt: null,
        isRelevant: null,
        stance: null,
        confidence: null,
      },
    ],
    isLoading: false,
  } as unknown as ReturnType<typeof useSocialAccountPosts>)
  vi.mocked(useBackfillSocialAccount).mockReturnValue(
    mutation(overrides.backfillMutate ?? mutateBackfill) as unknown as ReturnType<
      typeof useBackfillSocialAccount
    >,
  )
  vi.mocked(useImportSocialCookie).mockReturnValue(
    mutation(vi.fn().mockResolvedValue({ cookieJarsAvailable: 3 })) as unknown as ReturnType<
      typeof useImportSocialCookie
    >,
  )
  vi.mocked(useUpdateAsrConfig).mockReturnValue(
    mutation(vi.fn().mockResolvedValue({})) as unknown as ReturnType<
      typeof useUpdateAsrConfig
    >,
  )
  vi.mocked(useTestAsrConfig).mockReturnValue(
    mutation(vi.fn().mockResolvedValue({ ok: true, latencyMs: 120, text: 'ok', error: null })) as unknown as ReturnType<
      typeof useTestAsrConfig
    >,
  )
  return {
    updateMutate: overrides.updateMutate ?? mutate,
    deleteMutate: overrides.deleteMutate ?? mutateDelete,
    backfillMutate: overrides.backfillMutate ?? mutateBackfill,
  }
}

describe('SocialTracking 管理页', () => {
  it('渲染采集健康卡与账号表', () => {
    setupMocks()
    render(<SocialTracking />)
    expect(screen.getByText('抖音采集')).toBeInTheDocument()
    expect(screen.getByText('ASR 转写')).toBeInTheDocument()
    expect(screen.getByText('2 个可用')).toBeInTheDocument()
    expect(screen.getByText('财经大V-A')).toBeInTheDocument()
  })

  it('Switch 启停触发更新（isActive 传入）', async () => {
    const { updateMutate } = setupMocks()
    render(<SocialTracking />)
    fireEvent.click(screen.getByRole('switch'))
    await waitFor(() => {
      expect(updateMutate).toHaveBeenCalledWith({ id: 1, data: { isActive: false } })
    })
  })

  it('Popconfirm 确认后删除账号', async () => {
    const { deleteMutate } = setupMocks()
    render(<SocialTracking />)
    fireEvent.click(screen.getByRole('button', { name: /删 除|删除/ }))
    fireEvent.click(await screen.findByRole('button', { name: 'OK', hidden: true }))
    await waitFor(() => {
      expect(deleteMutate).toHaveBeenCalledWith(1)
    })
  })

  it('Popconfirm 确认后触发回填采集', async () => {
    const { backfillMutate } = setupMocks()
    render(<SocialTracking />)
    fireEvent.click(screen.getByRole('button', { name: /回 填|回填/ }))
    fireEvent.click(await screen.findByRole('button', { name: 'OK', hidden: true }))
    await waitFor(() => {
      expect(backfillMutate).toHaveBeenCalledWith(1)
    })
  })

  it('作品按钮打开排查抽屉并展示转写/判级状态', async () => {
    setupMocks()
    render(<SocialTracking />)
    fireEvent.click(screen.getByRole('button', { name: /作 品|作品/ }))
    expect(await screen.findByText('作品排查 · 财经大V-A')).toBeInTheDocument()
    expect(screen.getByText('今日复盘')).toBeInTheDocument()
    expect(screen.getByText('降级')).toBeInTheDocument()
    expect(screen.getByText('未判')).toBeInTheDocument()
  })
})
