import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/hooks/useAdminKb', () => ({
  useKbSources: vi.fn(),
  useKbOptimizationSuggestions: vi.fn(),
  useCreateKbOptimizationSuggestion: vi.fn(),
  useReviewKbOptimizationSuggestion: vi.fn(),
}))
vi.mock('@/hooks/useSkills', () => ({
  useSkillSquare: vi.fn(),
}))

import {
  useCreateKbOptimizationSuggestion,
  useKbOptimizationSuggestions,
  useKbSources,
  useReviewKbOptimizationSuggestion,
} from '@/hooks/useAdminKb'
import { useSkillSquare } from '@/hooks/useSkills'
import type { ApiKbOptimizationListResponse } from '@ai-invest/shared'

import { OptimizationTab } from './OptimizationTab'

const mockedSources = vi.mocked(useKbSources)
const mockedList = vi.mocked(useKbOptimizationSuggestions)
const mockedSquare = vi.mocked(useSkillSquare)
const mockedCreate = vi.mocked(useCreateKbOptimizationSuggestion)
const mockedReview = vi.mocked(useReviewKbOptimizationSuggestion)

const item = {
  targetFile: 'SKILL.md',
  section: '分析流程',
  originalText: '旧文',
  suggestedText: '新文',
  reason: '缺引用',
  citations: ['《价值投资课》 第3集 05:30-06:10'],
}

function listing(
  rows: Partial<ApiKbOptimizationListResponse['items'][number]>[]
): ApiKbOptimizationListResponse {
  return {
    total: rows.length,
    page: 1,
    pageSize: 10,
    items: rows.map((r, i) => ({
      id: i + 1,
      skillId: 'market-daily-review',
      skillLabel: '大盘复盘',
      skillKind: 'builtin',
      skillVersion: 3,
      sourceId: 1,
      sourceName: '价值投资课',
      status: 'pending_review',
      skillDefinition: null,
      suggestions: [item],
      summary: '加强引用',
      modelName: 'kimi/k2',
      error: null,
      reviewedBy: null,
      reviewedAt: null,
      reviewNote: null,
      applyResult: null,
      createdBy: 1,
      createdAt: '2026-09-21T00:00:00Z',
      updatedAt: '2026-09-21T00:00:00Z',
      ...r,
    })) as ApiKbOptimizationListResponse['items'],
  }
}

function mutationStub() {
  return { mutate: vi.fn(), mutateAsync: vi.fn().mockResolvedValue({}), isPending: false }
}

function setup(data?: ApiKbOptimizationListResponse) {
  mockedSources.mockReturnValue({
    data: [{ id: 1, name: '价值投资课', enabled: true }],
  } as never)
  mockedSquare.mockReturnValue({
    data: {
      available: [],
      mine: [
        {
          skillId: 'market-daily-review',
          label: '大盘复盘',
          kind: 'executable',
          scenario: 'market',
          isBuiltin: true,
          published: true,
          installed: false,
          enabled: null,
          description: null,
        },
      ],
    },
  } as never)
  mockedList.mockReturnValue({ data, isLoading: false } as never)
  const create = mutationStub()
  const review = mutationStub()
  mockedCreate.mockReturnValue(create as never)
  mockedReview.mockReturnValue(review as never)
  return { create, review }
}

async function expandFirstRow() {
  const icon = await waitFor(() => {
    const el = document.querySelector('.ant-table-row-expand-icon')
    if (!el) throw new Error('expand icon not rendered yet')
    return el
  })
  fireEvent.click(icon)
}

describe('OptimizationTab', () => {
  it('renders queue rows with status tag and review actions', async () => {
    setup(listing([{ status: 'pending_review' }]))
    render(<OptimizationTab />)
    expect(await screen.findByText('大盘复盘')).toBeInTheDocument()
    expect(screen.getByText('待审核')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /应\s*用/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /驱\s*回|驳\s*回/ })).toBeInTheDocument()
  })

  it('shows failure error text for failed rows without actions', async () => {
    setup(listing([{ status: 'failed', error: '模型未配置' }]))
    render(<OptimizationTab />)
    expect(await screen.findByText('模型未配置')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /应\s*用/ })).not.toBeInTheDocument()
  })

  it('reject opens note modal and requires reason', async () => {
    setup(listing([{ status: 'pending_review' }]))
    render(<OptimizationTab />)
    fireEvent.click(await screen.findByRole('button', { name: /驱\s*回|驳\s*回/ }))
    const modal = await screen.findByRole('dialog')
    expect(modal).toBeInTheDocument()
    const ok = await waitFor(() => {
      const btns = modal.querySelectorAll('.ant-btn-primary')
      const target = Array.from(btns).find((b) => b.textContent?.includes('驳'))
      if (!target) throw new Error('ok button not ready')
      return target
    })
    // 未填理由直接驳回：前端提示必填（placeholder 校验由后端 422 兜底，此处只验证弹窗行为）
    fireEvent.click(ok)
    await waitFor(() => {
      const review = mockedReview.mock.results[0]?.value as
        | { mutate: ReturnType<typeof vi.fn> }
        | undefined
      // 空理由不应发出 reject 请求（后端会 422）
      expect(review?.mutate).not.toHaveBeenCalled()
    })
  })

  it('apply opens confirm modal explaining builtin export semantics', async () => {
    setup(listing([{ status: 'pending_review', skillKind: 'builtin' }]))
    render(<OptimizationTab />)
    fireEvent.click(await screen.findByRole('button', { name: /应\s*用/ }))
    const modal = await screen.findByRole('dialog')
    expect(modal.textContent).toContain('运行时不改文件')
    expect(modal.textContent).toContain('交开发核对后落库')
  })

  it('custom apply modal states version bump semantics', async () => {
    setup(listing([{ status: 'pending_review', skillKind: 'custom' }]))
    render(<OptimizationTab />)
    fireEvent.click(await screen.findByRole('button', { name: /应\s*用/ }))
    const modal = await screen.findByRole('dialog')
    expect(modal.textContent).toContain('version+1')
  })

  it('expanded row shows suggestion detail with citation', async () => {
    setup(listing([{ status: 'pending_review' }]))
    render(<OptimizationTab />)
    await expandFirstRow()
    const cite = await screen.findByText(/《价值投资课》 第3集/)
    expect(cite).toBeInTheDocument()
    expect(screen.getByText(/缺引用/)).toBeInTheDocument()
  })

  it('builtin applied row exposes exported full text', async () => {
    setup(
      listing([
        {
          status: 'applied',
          applyResult: {
            kind: 'builtin_export',
            appliedCount: 1,
            files: [{ path: 'SKILL.md', content: '应用后全文' }],
          },
        },
      ])
    )
    render(<OptimizationTab />)
    await expandFirstRow()
    expect(
      await screen.findByText(/应用后全文 · SKILL.md（复制交开发落库）/)
    ).toBeInTheDocument()
  })
})
