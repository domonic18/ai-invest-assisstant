import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import { MarkdownText } from './MarkdownText'

describe('MarkdownText', () => {
  it('renders inline code as highlight', () => {
    render(<MarkdownText content={'关键数据 `2.66万亿` 值得关注'} />)
    const code = screen.getByText('2.66万亿')
    expect(code.tagName).toBe('CODE')
    expect(code.className).toContain('bg-amber-400/15')
  })

  it('colors signed percentages by cn scheme (red up / green down)', () => {
    render(<MarkdownText content={'沪指 +3.05% 创业板 -1.20%'} />)
    expect(screen.getByText('+3.05%').className).toContain('text-red-400')
    expect(screen.getByText('-1.20%').className).toContain('text-green-400')
  })

  it('renders bold and lists', () => {
    render(<MarkdownText content={'1. **重点** 第一项\n2. 第二项'} />)
    expect(screen.getByRole('list')).toBeInTheDocument()
    const bold = screen.getByText('重点')
    expect(bold.tagName).toBe('STRONG')
  })

  it('does not color percentages inside inline code', () => {
    render(<MarkdownText content={'数据 `+3.05%`'} />)
    expect(screen.getByText('+3.05%').tagName).toBe('CODE')
  })
})
