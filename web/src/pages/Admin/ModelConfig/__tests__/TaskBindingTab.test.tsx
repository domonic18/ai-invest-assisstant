import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'

import type { ApiTaskBindingSlot, LLMConfig } from '@ai-invest/shared'

import { TaskBindingTab } from '../TaskBindingTab'
import { useLLMConfigs, useReplaceTaskBindings, useTaskBindings } from '@/hooks/useModelConfig'

vi.mock('@/hooks/useModelConfig', () => ({
  useTaskBindings: vi.fn(),
  useLLMConfigs: vi.fn(),
  useReplaceTaskBindings: vi.fn(),
}))

const mockedTaskBindings = vi.mocked(useTaskBindings)
const mockedConfigs = vi.mocked(useLLMConfigs)
const mockedReplace = vi.mocked(useReplaceTaskBindings)

function slotFixture(overrides: Partial<ApiTaskBindingSlot> = {}): ApiTaskBindingSlot {
  return {
    taskKey: 'news_score',
    label: '新闻重要度分级',
    description: '电报快讯 AI 重要度打分（高频轻任务）',
    configId: null,
    configName: null,
    modelName: null,
    updatedAt: null,
    ...overrides,
  }
}

function configFixture(overrides: Partial<LLMConfig> = {}): LLMConfig {
  return {
    id: 1,
    name: 'DeepSeek Chat',
    provider: 'deepseek',
    protocol: 'openai',
    baseUrl: 'https://api.deepseek.com',
    modelName: 'deepseek-chat',
    apiKeyMasked: 'sk-***',
    isDefault: false,
    isActive: true,
    purpose: 'chat',
    backupConfigId: null,
    degradedUntil: null,
    extra: {},
    lastTestedAt: null,
    lastTestStatus: null,
    lastTestError: null,
    createdAt: '2026-10-13T00:00:00Z',
    updatedAt: '2026-10-13T00:00:00Z',
    ...overrides,
  }
}

function setup(
  slots: ApiTaskBindingSlot[],
  configs: LLMConfig[],
  mutateAsync: ReturnType<typeof vi.fn> = vi.fn().mockResolvedValue([]),
) {
  mockedTaskBindings.mockReturnValue({
    data: slots,
    isLoading: false,
  } as never)
  mockedConfigs.mockReturnValue({ data: configs } as never)
  mockedReplace.mockReturnValue({
    mutateAsync,
    isPending: false,
  } as never)
  render(<TaskBindingTab />)
  return { mutateAsync }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('TaskBindingTab', () => {
  const slots = [
    slotFixture(),
    slotFixture({ taskKey: 'market_daily_review', label: '每日大盘复盘', description: '重任务' }),
    slotFixture({
      taskKey: 'chain_refresh',
      label: '产业链图谱刷新',
      description: '产业链图谱周度 AI 刷新',
      configId: 2,
      configName: '旧绑定',
      modelName: 'old-model',
      updatedAt: '2026-10-13T00:00:00Z',
    }),
  ]

  it('渲染 GET 响应中的全部槽位（含说明与已绑定名）', () => {
    setup(slots, [
      configFixture(),
      configFixture({ id: 2, name: '旧绑定', modelName: 'old-model' }),
    ])

    expect(screen.getByText('新闻重要度分级')).toBeInTheDocument()
    expect(screen.getByText('每日大盘复盘')).toBeInTheDocument()
    expect(screen.getByText('产业链图谱刷新')).toBeInTheDocument()
    expect(screen.getByText('电报快讯 AI 重要度打分（高频轻任务）')).toBeInTheDocument()
    expect(screen.getByText('产业链图谱周度 AI 刷新')).toBeInTheDocument()
    expect(screen.getByText('旧绑定（old-model）')).toBeInTheDocument()
    expect(screen.getByText(/轻任务绑廉价模型/)).toBeInTheDocument()
  })

  it('Select 只列 chat 用途且启用的条目', () => {
    setup(slots, [
      configFixture({ id: 1, name: '可用对话', modelName: 'chat-1' }),
      configFixture({ id: 2, name: '停用对话', modelName: 'chat-2', isActive: false }),
      configFixture({ id: 3, name: '嵌入条目', modelName: 'embed-1', purpose: 'embedding' }),
    ])

    fireEvent.mouseDown(screen.getAllByRole('combobox')[0])

    expect(screen.getByText('可用对话（chat-1）')).toBeInTheDocument()
    expect(screen.queryByText('停用对话（chat-2）')).not.toBeInTheDocument()
    expect(screen.queryByText('嵌入条目（embed-1）')).not.toBeInTheDocument()
  })

  it('保存提交整表单：已选槽位带 id，未绑定槽位为 null', async () => {
    const { mutateAsync } = setup(slots, [configFixture({ id: 1 })])

    fireEvent.mouseDown(screen.getAllByRole('combobox')[0])
    fireEvent.click(screen.getByText('DeepSeek Chat（deepseek-chat）'))
    fireEvent.click(screen.getByRole('button', { name: /保存绑定/ }))

    await waitFor(() => expect(mutateAsync).toHaveBeenCalledTimes(1))
    const payload = mutateAsync.mock.calls[0][0] as {
      bindings: { taskKey: string; configId: number | null }[]
    }
    expect(payload.bindings).toHaveLength(3)
    expect(payload.bindings[0]).toEqual({ taskKey: 'news_score', configId: 1 })
    expect(payload.bindings[1]).toEqual({ taskKey: 'market_daily_review', configId: null })
    expect(payload.bindings[2]).toEqual({ taskKey: 'chain_refresh', configId: 2 })
    expect(await screen.findByText('任务模型绑定已保存')).toBeInTheDocument()
  })

  it('保存失败提示错误信息', async () => {
    setup(slots, [configFixture()], vi.fn().mockRejectedValue(new Error('校验失败')))

    fireEvent.click(screen.getByRole('button', { name: /保存绑定/ }))

    expect(await screen.findByText('校验失败')).toBeInTheDocument()
  })
})
