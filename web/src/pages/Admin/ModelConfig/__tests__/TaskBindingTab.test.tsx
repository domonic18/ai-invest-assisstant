import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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

// rc-select 关闭后的下拉仍挂载在 DOM（hidden），断言须限定在当前可见下拉内
function visibleDropdown(): HTMLElement {
  const dropdown = document.querySelector(
    '.ant-select-dropdown:not(.ant-select-dropdown-hidden)',
  )
  expect(dropdown).not.toBeNull()
  return dropdown as HTMLElement
}

function slotFixture(overrides: Partial<ApiTaskBindingSlot> = {}): ApiTaskBindingSlot {
  return {
    taskKey: 'news_score',
    label: '新闻重要度分级',
    description: '电报快讯 AI 重要度打分（高频轻任务）',
    purpose: 'chat',
    configId: null,
    configName: null,
    modelName: null,
    backupConfigId: null,
    backupConfigName: null,
    backupModelName: null,
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
    isActive: true,
    purpose: 'chat',
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
    }),
    slotFixture({
      taskKey: 'decision',
      label: '判断模型',
      description: '盘中执行 L1 判断',
      purpose: 'decision',
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
    expect(screen.getByText(/每槽位绑定主模型/)).toBeInTheDocument()
  })

  it('Select 候选按槽位 purpose 过滤且仅列启用条目', () => {
    setup(slots, [
      configFixture({ id: 1, name: '可用对话', modelName: 'chat-1' }),
      configFixture({ id: 2, name: '停用对话', modelName: 'chat-2', isActive: false }),
      configFixture({ id: 3, name: '嵌入条目', modelName: 'embed-1', purpose: 'embedding' }),
      configFixture({
        id: 4,
        name: '判断条目',
        modelName: 'jev-latest',
        purpose: 'decision',
      }),
    ])

    // combobox 顺序：每槽位「主模型、备用模型」两个 select 依次排列
    fireEvent.mouseDown(screen.getAllByRole('combobox')[0])
    const chatDropdown = visibleDropdown()
    expect(within(chatDropdown).getByText('可用对话（chat-1）')).toBeInTheDocument()
    expect(within(chatDropdown).queryByText('停用对话（chat-2）')).not.toBeInTheDocument()
    expect(within(chatDropdown).queryByText('嵌入条目（embed-1）')).not.toBeInTheDocument()
    expect(within(chatDropdown).queryByText('判断条目（jev-latest）')).not.toBeInTheDocument()

    // decision 槽位的主模型 select（第 7 个 combobox，3 槽 × 2 + 1）只列 decision 条目
    fireEvent.mouseDown(screen.getAllByRole('combobox')[6])
    const decisionDropdown = visibleDropdown()
    expect(within(decisionDropdown).getByText('判断条目（jev-latest）')).toBeInTheDocument()
    expect(within(decisionDropdown).queryByText('可用对话（chat-1）')).not.toBeInTheDocument()
  })

  it('主模型必填：未选时保存被拦截', async () => {
    const { mutateAsync } = setup(slots, [configFixture()])

    fireEvent.click(screen.getByRole('button', { name: /保存绑定/ }))

    await waitFor(() =>
      expect(screen.getAllByText('请选择主模型').length).toBeGreaterThan(0),
    )
    expect(mutateAsync).not.toHaveBeenCalled()
  })

  // 四次下拉交互 + 整表单校验在并行满载下耗时 >15s 默认超时，单独放宽
  it(
    '保存提交整表单：主备字段成对提交，未选备用的为 null',
    { timeout: 45000 },
    async () => {
    const { mutateAsync } = setup(slots, [
      configFixture({ id: 1, name: '主模型A', modelName: 'a-1' }),
      configFixture({ id: 2, name: '旧绑定', modelName: 'old-model' }),
      configFixture({ id: 3, name: '备用模型B', modelName: 'b-1' }),
      configFixture({
        id: 4,
        name: '判断条目',
        modelName: 'jev-latest',
        purpose: 'decision',
      }),
    ])

    const selectOption = async (comboboxIndex: number, optionLabel: string) => {
      fireEvent.mouseDown(screen.getAllByRole('combobox')[comboboxIndex])
      const dropdown = await waitFor(() => visibleDropdown(), { timeout: 5000 })
      fireEvent.click(within(dropdown).getByText(optionLabel))
    }
    await selectOption(0, '主模型A（a-1）') // 槽位 0（news_score）主模型
    await selectOption(1, '备用模型B（b-1）') // 槽位 0 备用模型
    await selectOption(2, '主模型A（a-1）') // 槽位 1（market_daily_review）主模型
    await selectOption(6, '判断条目（jev-latest）') // 槽位 3（decision）主模型

    fireEvent.click(screen.getByRole('button', { name: /保存绑定/ }))

    await waitFor(() => expect(mutateAsync).toHaveBeenCalledTimes(1), { timeout: 5000 })
    const payload = mutateAsync.mock.calls[0][0] as {
      bindings: { taskKey: string; configId: number; backupConfigId: number | null }[]
    }
    expect(payload.bindings).toHaveLength(4)
    expect(payload.bindings[0]).toEqual({
      taskKey: 'news_score',
      configId: 1,
      backupConfigId: 3,
    })
    expect(payload.bindings[1]).toEqual({
      taskKey: 'market_daily_review',
      configId: 1,
      backupConfigId: null,
    })
    expect(payload.bindings[2]).toEqual({
      taskKey: 'chain_refresh',
      configId: 2,
      backupConfigId: null,
    })
    expect(payload.bindings[3]).toEqual({
      taskKey: 'decision',
      configId: 4,
      backupConfigId: null,
    })
    expect(await screen.findByText('任务模型绑定已保存')).toBeInTheDocument()
    },
  )

  it('保存失败提示错误信息', async () => {
    setup(
      slots.slice(0, 1).map((s) => ({ ...s, configId: 1 })),
      [configFixture()],
      vi.fn().mockRejectedValue(new Error('校验失败')),
    )

    fireEvent.click(screen.getByRole('button', { name: /保存绑定/ }))

    expect(await screen.findByText('校验失败')).toBeInTheDocument()
  })
})
