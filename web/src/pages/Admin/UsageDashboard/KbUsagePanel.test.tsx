import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/hooks/useAdminKb', () => ({
  useKbSources: vi.fn(),
  useKbUsage: vi.fn(),
  useKbSettings: vi.fn(),
  useUpdateKbSettings: vi.fn(),
}))

import {
  useKbSettings,
  useKbSources,
  useKbUsage,
  useUpdateKbSettings,
} from '@/hooks/useAdminKb'
import type { ApiKbUsageResponse } from '@ai-invest/shared'

import { KbUsagePanel } from './KbUsagePanel'

const mockedSources = vi.mocked(useKbSources)
const mockedUsage = vi.mocked(useKbUsage)
const mockedSettings = vi.mocked(useKbSettings)
const mockedUpdate = vi.mocked(useUpdateKbSettings)

const usage: ApiKbUsageResponse = {
  sourceId: null,
  dateFrom: null,
  dateTo: null,
  currency: 'CNY',
  tokenItems: [
    {
      feature: 'kb_clean',
      modelName: 'minimax-m3',
      calls: 2,
      promptTokens: 1000,
      completionTokens: 500,
      totalTokens: 4500,
      estimatedCost: null,
    },
    {
      feature: 'kb_vision',
      modelName: 'glm-4v',
      calls: 2,
      promptTokens: 1700,
      completionTokens: 700,
      totalTokens: 2400,
      estimatedCost: 0.04,
    },
  ],
  asr: {
    mediaCount: 3,
    audioSeconds: 5460.5,
    estimatedSeconds: 5400,
    costPerHour: 0.3,
    cost: 0.455,
  },
  cleanTokensPredicted: 14400,
  cleanTokensActual: 4500,
  totalCost: 0.495,
}

describe('KbUsagePanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedSettings.mockReturnValue({ data: undefined } as never)
    mockedUpdate.mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as never)
  })

  it('渲染统计卡、分项表与 ASR/对照明细', () => {
    mockedSources.mockReturnValue({ data: [{ id: 1, name: '价值投资课' }] } as never)
    mockedUsage.mockReturnValue({ data: usage, isLoading: false } as never)

    const { container } = render(<KbUsagePanel />)

    expect(mockedUsage).toHaveBeenCalledWith(null, null, null)
    // 统计卡：合计费用 / ASR 时长 / 已转写素材 / 清洗 token 预估/实际
    expect(container.textContent).toContain('0.495')
    expect(container.textContent).toContain('1.5') // 5460.5s ≈ 1.5 小时
    expect(container.textContent).toContain('3')
    expect(container.textContent).toContain('14,400 / 4,500')
    // 分项表：feature 标签映射 + 千分位 + 视觉估算费用
    expect(screen.getByText('清洗')).toBeInTheDocument()
    expect(screen.getByText('视觉')).toBeInTheDocument()
    expect(screen.getByText('minimax-m3')).toBeInTheDocument()
    expect(screen.getByText('4,500')).toBeInTheDocument()
    expect(screen.getByText('2,400')).toBeInTheDocument()
    expect(screen.getByText('0.0400')).toBeInTheDocument()
    // ASR 明细
    expect(screen.getByText('0.3 元/小时')).toBeInTheDocument()
    expect(screen.getByText('0.455 元')).toBeInTheDocument()
    // 对照
    expect(screen.getByText(/14,400（约 1\.4 万）/)).toBeInTheDocument()
    expect(screen.getByText(/4,500（约 0\.5 万）/)).toBeInTheDocument()
  })

  it('计价设置弹窗回填现值并提交合并后的 unitPrices', async () => {
    mockedSources.mockReturnValue({ data: [] } as never)
    mockedUsage.mockReturnValue({ data: usage, isLoading: false } as never)
    mockedSettings.mockReturnValue({
      data: { unitPrices: { asrPerHour: 0.3, vlmPerImage: 0.02 } },
    } as never)
    const mutateAsync = vi.fn().mockResolvedValue({})
    mockedUpdate.mockReturnValue({ mutateAsync, isPending: false } as never)

    render(<KbUsagePanel />)
    fireEvent.click(screen.getByRole('button', { name: /计\s*价\s*设\s*置/ }))

    const modal = await screen.findByRole('dialog')
    await waitFor(() => {
      expect((modal.querySelector('input#asrPerHour') as HTMLInputElement)?.value).toBe('0.3')
    })
    fireEvent.change(modal.querySelector('input#asrPerHour') as HTMLInputElement, {
      target: { value: '0.5' },
    })
    fireEvent.click(
      Array.from(modal.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('保')
      ) as HTMLButtonElement
    )

    await waitFor(() =>
      expect(mutateAsync).toHaveBeenCalledWith({
        unitPrices: { asrPerHour: 0.5, vlmPerImage: 0.02 },
      })
    )
  })

  it('单价未配置时费用项降级展示', () => {
    mockedSources.mockReturnValue({ data: [] } as never)
    mockedUsage.mockReturnValue({
      data: {
        ...usage,
        tokenItems: [{ ...usage.tokenItems[0], estimatedCost: null }],
        asr: { ...usage.asr, costPerHour: null, cost: null },
        totalCost: 0,
      },
      isLoading: false,
    } as never)

    const { container } = render(<KbUsagePanel />)

    expect(screen.getByText('未配置')).toBeInTheDocument()
    expect(container.textContent).toContain('0.0000') // Statistic precision=4
    expect(screen.getByText(/未配置单价/)).toBeInTheDocument()
  })
})
