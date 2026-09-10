import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { ApiNewsChannel } from '@ai-invest/shared'

import { ChannelMonitorBar } from './ChannelMonitorBar'

function channel(overrides: Partial<ApiNewsChannel>): ApiNewsChannel {
  return {
    key: 'cls_telegraph',
    name: '财联社电报',
    status: 'live',
    statusText: 'LIVE 采集中',
    pollDesc: '10s 增量轮询 · 驻留进程',
    todayCount: 328,
    lastUpdatedAt: '2026-09-08T04:03:45Z',
    lagSeconds: 15,
    ...overrides,
  }
}

describe('ChannelMonitorBar', () => {
  it('renders one card per registered channel, driven by response data', () => {
    render(
      <ChannelMonitorBar
        channels={[
          channel({}),
          channel({
            key: 'eastmoney_flash_news',
            name: '东财快讯',
            status: 'ok',
            statusText: '正常运行',
            pollDesc: '30 分钟轮询',
            todayCount: 96,
            lagSeconds: 600,
          }),
          channel({
            key: 'x_video',
            name: 'X 博主',
            status: 'delayed',
            statusText: '采集延迟',
            todayCount: 0,
          }),
        ]}
      />,
    )
    expect(screen.getByText('财联社电报')).toBeInTheDocument()
    expect(screen.getByText('东财快讯')).toBeInTheDocument()
    expect(screen.getByText('X 博主')).toBeInTheDocument()
    expect(screen.getByText('LIVE 采集中')).toBeInTheDocument()
    // 滞后分钟数换算（600s -> 10min）
    expect(screen.getByText(/10min/)).toBeInTheDocument()
  })

  it('renders nothing when channels are empty', () => {
    const { container } = render(<ChannelMonitorBar channels={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})
