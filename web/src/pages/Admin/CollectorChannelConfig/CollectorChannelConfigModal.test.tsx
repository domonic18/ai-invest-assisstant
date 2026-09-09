import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type {
  CollectorChannelConfig,
  CollectorChannelConfigFormValues,
  ProxyConfig,
} from '@ai-invest/shared'

vi.mock('@/hooks/useProxyConfigs', () => ({
  useProxyConfigs: vi.fn(),
}))

import { useProxyConfigs } from '@/hooks/useProxyConfigs'

import { CollectorChannelConfigModal } from './CollectorChannelConfigModal'

const mockProxyConfigs = vi.mocked(useProxyConfigs)

const proxies: ProxyConfig[] = [
  {
    id: 3,
    name: 'frp-clash',
    protocol: 'http',
    host: '175.27.167.123',
    port: 17890,
    username: 'collector',
    passwordMasked: '********',
    isEnabled: true,
    createdAt: '2026-09-09T00:00:00Z',
    updatedAt: '2026-09-09T00:00:00Z',
  },
]

const boundChannel: CollectorChannelConfig = {
  id: 1,
  source: 'yahoo',
  name: 'Yahoo Finance',
  baseUrl: 'https://query1.finance.yahoo.com',
  apiKeyMasked: null,
  isEnabled: true,
  supportedDataTypes: ['global-index'],
  extra: {},
  proxyConfigId: 3,
  createdAt: '2026-09-09T00:00:00Z',
  updatedAt: '2026-09-09T00:00:00Z',
}

function setup(overrides: Partial<Parameters<typeof CollectorChannelConfigModal>[0]> = {}) {
  const onSubmit = vi.fn()
  render(
    <CollectorChannelConfigModal
      open
      editing={null}
      onCancel={vi.fn()}
      onSubmit={onSubmit}
      loading={false}
      {...overrides}
    />,
  )
  return { onSubmit }
}

describe('CollectorChannelConfigModal 代理绑定', () => {
  it('渲染代理下拉选项（含直连占位与代理名）', () => {
    mockProxyConfigs.mockReturnValue({
      data: proxies,
      isLoading: false,
    } as unknown as ReturnType<typeof useProxyConfigs>)

    setup()

    expect(screen.getByText('代理服务器')).toBeInTheDocument()
    expect(screen.getByText('直连（不使用代理）')).toBeInTheDocument()
  })

  it('编辑已绑定渠道回显代理并随表单提交', async () => {
    mockProxyConfigs.mockReturnValue({
      data: proxies,
      isLoading: false,
    } as unknown as ReturnType<typeof useProxyConfigs>)

    const { onSubmit } = setup({ editing: boundChannel })

    // Select 回显选中项 label（含主机:端口；Form 回显为异步）
    expect(
      await screen.findByText('frp-clash（175.27.167.123:17890）'),
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'OK', hidden: true }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1))

    const values = onSubmit.mock.calls[0][0] as CollectorChannelConfigFormValues
    expect(values.proxyConfigId).toBe(3)
  })
})
