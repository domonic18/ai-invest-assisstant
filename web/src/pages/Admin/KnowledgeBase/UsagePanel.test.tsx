import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/hooks/useAdminKb', () => ({
  useKbSources: vi.fn(),
  useKbUsage: vi.fn(),
}))

import { useKbSources, useKbUsage } from '@/hooks/useAdminKb'
import type { ApiKbUsageResponse } from '@ai-invest/shared'

import { UsagePanel } from './UsagePanel'

const mockedSources = vi.mocked(useKbSources)
const mockedUsage = vi.mocked(useKbUsage)

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

describe('UsagePanel', () => {
  it('渲染 token 分项表与 ASR/对照汇总', () => {
    mockedSources.mockReturnValue({ data: [{ id: 1, name: '价值投资课' }] } as never)
    mockedUsage.mockReturnValue({ data: usage, isLoading: false } as never)

    const { container } = render(<UsagePanel />)

    expect(mockedUsage).toHaveBeenCalledWith(null, null, null)
    // 分项表：feature 标签映射 + 数字千分位 + 视觉估算费用
    expect(screen.getByText('清洗')).toBeInTheDocument()
    expect(screen.getByText('视觉')).toBeInTheDocument()
    expect(screen.getByText('minimax-m3')).toBeInTheDocument()
    expect(screen.getByText('4,500')).toBeInTheDocument()
    expect(screen.getByText('2,400')).toBeInTheDocument()
    expect(screen.getByText('0.0400')).toBeInTheDocument()
    // ASR 汇总
    expect(screen.getByText('3 个')).toBeInTheDocument()
    expect(screen.getByText('0.3 元/小时')).toBeInTheDocument()
    expect(screen.getByText('0.455 元')).toBeInTheDocument()
    // 预估 vs 实际对照（formatTokens 全文）
    expect(screen.getByText(/14,400（约 1\.4 万）/)).toBeInTheDocument()
    expect(screen.getByText(/4,500（约 0\.5 万）/)).toBeInTheDocument()
    // 合计
    expect(container.textContent).toContain('合计费用：0.495 CNY')
  })

  it('单价未配置时费用项降级展示', () => {
    mockedSources.mockReturnValue({ data: [] } as never)
    mockedUsage.mockReturnValue({
      data: {
        ...usage,
        tokenItems: [
          { ...usage.tokenItems[0], estimatedCost: null },
        ],
        asr: { ...usage.asr, costPerHour: null, cost: null },
        totalCost: 0,
      },
      isLoading: false,
    } as never)

    const { container } = render(<UsagePanel />)

    expect(screen.getByText('未配置')).toBeInTheDocument()
    expect(container.textContent).toContain('合计费用：0 CNY')
  })
})
