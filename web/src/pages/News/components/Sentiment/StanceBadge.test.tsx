/** StanceBadge：红涨绿跌配色随 colorScheme 翻转（cn=红多绿空 / us=绿多红空）。 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { useSettingsStore } from '@/stores/settings'

import { StanceBadge } from './StanceBadge'

describe('StanceBadge', () => {
  it('renders bullish with cn-scheme rise color (red)', () => {
    useSettingsStore.setState({ colorScheme: 'cn' })
    render(<StanceBadge stance="bullish" confidence={0.9} />)
    const badge = screen.getByText('看多')
    expect(badge.style.color).toBe('rgb(248, 81, 73)')
    expect(badge.getAttribute('title')).toBe('置信度 90%')
  })

  it('flips bullish to green in us scheme', () => {
    useSettingsStore.setState({ colorScheme: 'us' })
    render(<StanceBadge stance="bullish" />)
    expect(screen.getByText('看多').style.color).toBe('rgb(46, 160, 67)')
  })

  it('renders bearish with cn-scheme fall color (green)', () => {
    useSettingsStore.setState({ colorScheme: 'cn' })
    render(<StanceBadge stance="bearish" />)
    expect(screen.getByText('看空').style.color).toBe('rgb(46, 160, 67)')
  })

  it('renders bearish red in us scheme', () => {
    useSettingsStore.setState({ colorScheme: 'us' })
    render(<StanceBadge stance="bearish" />)
    expect(screen.getByText('看空').style.color).toBe('rgb(248, 81, 73)')
  })

  it('renders neutral gray regardless of scheme', () => {
    useSettingsStore.setState({ colorScheme: 'cn' })
    const { rerender } = render(<StanceBadge stance="neutral" />)
    expect(screen.getByText('中性').style.color).toBe('rgb(140, 140, 140)')
    useSettingsStore.setState({ colorScheme: 'us' })
    rerender(<StanceBadge stance="neutral" />)
    expect(screen.getByText('中性').style.color).toBe('rgb(140, 140, 140)')
  })
})
