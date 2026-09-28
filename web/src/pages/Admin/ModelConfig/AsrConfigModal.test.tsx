import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'

import type { ApiAsrConfig } from '@ai-invest/shared'

import { AsrConfigModal } from './AsrConfigModal'

function fixture(overrides: Partial<ApiAsrConfig> = {}): ApiAsrConfig {
  return {
    provider: 'minimax',
    protocol: 'minimax',
    baseUrl: 'https://api.minimaxi.com',
    model: 'asr-1.0',
    apiKeyMasked: 'sk-1****abcd',
    apiKeyConfigured: true,
    maxAudioSeconds: 600,
    hotwords: ['美联储'],
    enabled: false,
    updatedAt: '2026-09-28T00:00:00Z',
    ...overrides,
  }
}

function setup(config: ApiAsrConfig | null) {
  const onSubmit = vi.fn()
  // 弹窗内部 useTestAsrConfig 依赖 react-query 上下文
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <AsrConfigModal
        open
        config={config}
        loading={false}
        onCancel={vi.fn()}
        onSubmit={onSubmit}
      />
    </QueryClientProvider>,
  )
  return { onSubmit }
}

// Modal appear 动画态 footer 按钮不在可访问树内，须 hidden 查询；
// antd Button 对双字中文自动插空格（「保 存」），name 用正则
const clickSave = () =>
  fireEvent.click(screen.getByRole('button', { name: /保\s*存/, hidden: true }))

// 表单 combobox 顺序：供应商 → 调用协议
const selectProvider = (label: string) => {
  fireEvent.mouseDown(screen.getAllByRole('combobox')[0])
  fireEvent.click(screen.getByText(label))
}

describe('AsrConfigModal', () => {
  it('预设供应商锁定协议：MiniMax 存量配置协议锁定且保存载荷完整', async () => {
    const { onSubmit } = setup(fixture())

    expect(document.querySelector('.ant-select-disabled')).not.toBeNull()
    expect(screen.getByLabelText(/Base URL/)).toHaveValue('https://api.minimaxi.com')
    expect(screen.getByText('MiniMax 专有')).toBeInTheDocument()

    clickSave()
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1))
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      provider: 'minimax',
      protocol: 'minimax',
      baseUrl: 'https://api.minimaxi.com',
      model: 'asr-1.0',
    })
  })

  it('选预设供应商自动填充地址/模型并派生协议', () => {
    setup(fixture())

    selectProvider('硅基流动')

    expect(screen.getByLabelText(/Base URL/)).toHaveValue('https://api.siliconflow.cn/v1')
    expect(screen.getByLabelText(/模型/)).toHaveValue('FunAudioLLM/SenseVoiceSmall')
    expect(screen.getByText('OpenAI 兼容')).toBeInTheDocument()
    expect(document.querySelector('.ant-select-disabled')).not.toBeNull() // 协议仍锁定
  })

  it('自定义供应商协议可选，手填地址不被覆盖', () => {
    setup(fixture({ provider: 'custom', protocol: 'openai' }))

    expect(document.querySelector('.ant-select-disabled')).toBeNull()
    expect(screen.getByText('自定义')).toBeInTheDocument()

    fireEvent.mouseDown(screen.getAllByRole('combobox')[1])
    fireEvent.click(screen.getByText('MiniMax 专有'))
    // 选中值展示与下拉选项同文本并存，断言出现即可
    expect(screen.getAllByText('MiniMax 专有').length).toBeGreaterThan(0)
  })

  it('存量未知 provider 按「自定义」展示且协议不锁定', () => {
    setup(fixture({ provider: 'my-relay', protocol: 'openai' }))

    expect(screen.getByText('自定义')).toBeInTheDocument()
    expect(document.querySelector('.ant-select-disabled')).toBeNull()
    expect(screen.getByLabelText(/Base URL/)).toHaveValue('https://api.minimaxi.com')
  })
})
