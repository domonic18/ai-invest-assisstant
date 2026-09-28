import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { LLM_PROVIDER_PRESETS } from '@ai-invest/shared'
import type { LLMConfig, LLMProtocol, LlmPurpose } from '@ai-invest/shared'

import { ModelFormModal } from './ModelFormModal'
import { chatProtocolForProvider, protocolForPurpose, resolvePresetBaseUrl } from './protocolRules'

function fixture(overrides: Partial<LLMConfig> = {}): LLMConfig {
  return {
    id: 1,
    name: 'DeepSeek Chat',
    provider: 'deepseek',
    protocol: 'openai',
    baseUrl: 'https://api.deepseek.com',
    modelName: 'deepseek-chat',
    apiKeyMasked: 'sk-***',
    isDefault: true,
    isActive: true,
    purpose: 'chat',
    backupConfigId: null,
    degradedUntil: null,
    extra: {},
    lastTestedAt: null,
    lastTestStatus: null,
    lastTestError: null,
    createdAt: '2026-09-28T00:00:00Z',
    updatedAt: '2026-09-28T00:00:00Z',
    ...overrides,
  }
}

function setup(editing: LLMConfig | null) {
  const onSubmit = vi.fn()
  render(
    <ModelFormModal
      open
      editing={editing}
      onCancel={vi.fn()}
      onSubmit={onSubmit}
      onTest={vi.fn()}
      testing={false}
      loading={false}
    />,
  )
  return { onSubmit }
}

// Modal 处于 appear 动画态时 footer 按钮不在可访问树内，须 hidden 查询；
// antd Button 对双字中文文案自动插空格（「确 定」），name 用正则匹配
const clickOk = () =>
  fireEvent.click(screen.getByRole('button', { name: /确\s*定/, hidden: true }))

// 表单 combobox 顺序：用途 → 调用协议 → 供应商
const selectPurpose = (label: string) => {
  fireEvent.mouseDown(screen.getAllByRole('combobox')[0])
  fireEvent.click(screen.getByText(label))
}

describe('protocolForPurpose（与后端 normalize_purpose_protocol 对偶规则一致）', () => {
  it.each([
    ['decision', 'deepseek', 'anthropic', 'systemone'],
    ['embedding', 'custom', 'anthropic', 'openai'],
    ['chat', 'deepseek', 'openai', 'openai'],
    ['vision', 'anthropic', 'anthropic', 'anthropic'],
  ] as [LlmPurpose, string, LLMProtocol, LLMProtocol][])(
    '%s + 现值 %s → %s',
    (purpose, provider, current, expected) => {
      expect(protocolForPurpose(purpose, provider, current)).toBe(expected)
    },
  )

  it('chat 带着从 decision 带来的 systemone 时按供应商回落', () => {
    expect(protocolForPurpose('chat', 'deepseek', 'systemone')).toBe('openai')
    expect(protocolForPurpose('chat', 'anthropic', 'systemone')).toBe('anthropic')
    // openrouter/codiv 预设是 systemone 渠道，跑对话走 OpenAI 兼容端点
    expect(chatProtocolForProvider('openrouter')).toBe('openai')
    expect(chatProtocolForProvider('codiv')).toBe('openai')
    expect(chatProtocolForProvider('kimi')).toBe('anthropic')
  })
})

describe('resolvePresetBaseUrl（国内主流厂商双协议端点联动）', () => {
  it('有协议专有端点的厂商按协议解析，默认协议回落 baseUrl', () => {
    expect(resolvePresetBaseUrl(LLM_PROVIDER_PRESETS.deepseek, 'openai')).toBe(
      'https://api.deepseek.com',
    )
    expect(resolvePresetBaseUrl(LLM_PROVIDER_PRESETS.deepseek, 'anthropic')).toBe(
      'https://api.deepseek.com/anthropic',
    )
    expect(resolvePresetBaseUrl(LLM_PROVIDER_PRESETS.minimax, 'anthropic')).toBe(
      'https://api.minimaxi.com/anthropic',
    )
    expect(resolvePresetBaseUrl(LLM_PROVIDER_PRESETS.zhipu, 'anthropic')).toBe(
      'https://open.bigmodel.cn/api/anthropic',
    )
    expect(resolvePresetBaseUrl(LLM_PROVIDER_PRESETS.kimi, 'anthropic')).toBe(
      'https://api.kimi.com/coding',
    )
    expect(resolvePresetBaseUrl(LLM_PROVIDER_PRESETS.kimi, 'openai')).toBe(
      'https://api.moonshot.cn/v1',
    )
  })

  it('无专有映射的预设（openai/anthropic/systemone 渠道）一律回落 baseUrl', () => {
    expect(resolvePresetBaseUrl(LLM_PROVIDER_PRESETS.openai, 'openai')).toBe(
      'https://api.openai.com/v1',
    )
    expect(resolvePresetBaseUrl(LLM_PROVIDER_PRESETS.anthropic, 'anthropic')).toBe(
      'https://api.anthropic.com',
    )
    expect(resolvePresetBaseUrl(LLM_PROVIDER_PRESETS.openrouter, 'systemone')).toBe(
      'https://openrouter.ai/api',
    )
  })
})

describe('ModelFormModal', () => {
  it('decision 条目：协议锁定 System One，隐藏默认/视觉开关，载荷不含备用键', async () => {
    const { onSubmit } = setup(
      fixture({ purpose: 'decision', protocol: 'systemone', modelName: 'jev-latest' }),
    )

    expect(document.querySelector('.ant-select-disabled')).not.toBeNull()
    expect(screen.getByText('System One')).toBeInTheDocument()
    expect(screen.queryByText('设为默认')).not.toBeInTheDocument()
    expect(screen.queryByText('视觉能力')).not.toBeInTheDocument()

    clickOk()
    // handleOk 异步：validateFields 完成后才回调 onSubmit
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1))
    const values = onSubmit.mock.calls[0][0] as Record<string, unknown>
    expect(values.purpose).toBe('decision')
    expect(values.protocol).toBe('systemone')
    expect(values).not.toHaveProperty('backupConfigId')
  })

  it('用途切到向量嵌入：协议自动派生为 OpenAI 兼容并锁定', () => {
    setup(fixture())

    expect(document.querySelector('.ant-select-disabled')).toBeNull()
    selectPurpose('向量嵌入（知识库检索）')

    expect(document.querySelector('.ant-select-disabled')).not.toBeNull()
    expect(screen.getByText('OpenAI 兼容')).toBeInTheDocument()
    expect(screen.queryByText('设为默认')).not.toBeInTheDocument()
  })

  it('用途切到视觉识别：视觉能力开关自动开启', () => {
    // isDefault/isActive 均关，保证切 vision 前无任何勾选态开关
    setup(fixture({ isDefault: false, isActive: false }))

    expect(screen.getByText('视觉能力')).toBeInTheDocument() // chat 用途本就显示该开关
    expect(document.querySelector('.ant-switch-checked')).toBeNull()
    selectPurpose('视觉识别（图片理解）')

    expect(document.querySelector('.ant-switch-checked')).not.toBeNull()
  })

  it('协议切到 Anthropic：预设供应商 Base URL 联动为协议专有端点', () => {
    setup(fixture()) // deepseek + openai

    const baseUrl = screen.getByLabelText(/API 地址/)
    expect(baseUrl).toHaveValue('https://api.deepseek.com')
    // 表单 combobox 顺序：用途 → 调用协议 → 供应商
    fireEvent.mouseDown(screen.getAllByRole('combobox')[1])
    fireEvent.click(screen.getByText('Anthropic'))

    expect(baseUrl).toHaveValue('https://api.deepseek.com/anthropic')
  })

  it('自定义供应商：切协议不覆盖手填 Base URL', () => {
    setup(fixture({ provider: 'custom', baseUrl: 'https://my-gateway.example.com' }))

    fireEvent.mouseDown(screen.getAllByRole('combobox')[1])
    fireEvent.click(screen.getByText('Anthropic'))

    expect(screen.getByLabelText(/API 地址/)).toHaveValue('https://my-gateway.example.com')
  })

  it('用途切到向量嵌入：协议派生 OpenAI 且 Base URL 跟随协议切换', () => {
    // kimi 预设为 anthropic 订阅端点，embedding 派生 openai 后应联动到按量平台端点
    setup(
      fixture({ provider: 'kimi', protocol: 'anthropic', baseUrl: 'https://api.kimi.com/coding' }),
    )

    selectPurpose('向量嵌入（知识库检索）')

    expect(screen.getByLabelText(/API 地址/)).toHaveValue('https://api.moonshot.cn/v1')
  })
})
