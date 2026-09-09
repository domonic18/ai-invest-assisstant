import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { ProxyConfig, ProxyConfigFormValues } from '@ai-invest/shared'

import { ProxyConfigModal } from './ProxyConfigModal'

const editing: ProxyConfig = {
  id: 1,
  name: 'Mac mini Clash',
  protocol: 'http',
  host: '175.27.167.123',
  port: 17890,
  username: 'collector',
  passwordMasked: '********',
  isEnabled: true,
  createdAt: '2026-09-09T00:00:00Z',
  updatedAt: '2026-09-09T00:00:00Z',
}

function setup(overrides: Partial<Parameters<typeof ProxyConfigModal>[0]> = {}) {
  const onSubmit = vi.fn()
  render(
    <ProxyConfigModal
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

// Modal 处于 appear 动画态时 footer 按钮不在可访问树内，须 hidden 查询
const clickOk = () =>
  fireEvent.click(screen.getByRole('button', { name: 'OK', hidden: true }))

describe('ProxyConfigModal', () => {
  it('编辑模式密码留空可提交（表示不修改）', async () => {
    const { onSubmit } = setup({ editing })

    expect(screen.getByDisplayValue('Mac mini Clash')).toBeInTheDocument()
    expect(screen.getByDisplayValue('17890')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('留空表示不修改')).toBeInTheDocument()

    clickOk()
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1))

    const values = onSubmit.mock.calls[0][0] as ProxyConfigFormValues
    expect(values.password).toBe('')
    expect(values.name).toBe('Mac mini Clash')
    expect(values.protocol).toBe('http')
    expect(values.port).toBe(17890)
    expect(values.isEnabled).toBe(true)
  })

  it('新建模式密码可留空提交（代理允许无鉴权）', async () => {
    const { onSubmit } = setup()

    fireEvent.change(screen.getByLabelText('名称'), { target: { value: '新代理' } })
    fireEvent.change(screen.getByLabelText('主机'), { target: { value: '1.2.3.4' } })
    fireEvent.change(screen.getByLabelText('端口'), { target: { value: '7890' } })
    clickOk()

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1))

    const values = onSubmit.mock.calls[0][0] as ProxyConfigFormValues
    // 未触碰的字段 antd 不写入 values（undefined），页面映射 || undefined 后省略
    expect(values.password ?? '').toBe('')
    expect(values.username ?? '').toBe('')
  })
})
