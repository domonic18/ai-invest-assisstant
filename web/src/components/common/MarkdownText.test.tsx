import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import { MarkdownText } from './MarkdownText'
import { fallHexSoft, riseHexSoft } from '@/utils/formatters'

// jsdom 将内联 style.color 归一为 rgb() 形式，hex 期望值同构换算后比较
const rgb = (hex: string) => {
  const n = parseInt(hex.slice(1), 16)
  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`
}

describe('MarkdownText', () => {
  it('renders inline code as highlight', () => {
    render(<MarkdownText content={'关键数据 `2.66万亿` 值得关注'} />)
    const code = screen.getByText('2.66万亿')
    expect(code.tagName).toBe('CODE')
    expect(code.className).toContain('bg-sky-400/10')
  })

  it('colors signed percentages by cn scheme (red up / green down)', () => {
    render(<MarkdownText content={'沪指 +3.05% 创业板 -1.20%'} />)
    // 涨跌色唯一 API 是 hex 系 helper：断言内联 style 与 helper 输出一致
    expect(screen.getByText('+3.05%').style.color).toBe(rgb(riseHexSoft()))
    expect(screen.getByText('-1.20%').style.color).toBe(rgb(fallHexSoft()))
  })

  it('renders bold and lists', () => {
    render(<MarkdownText content={'1. **重点** 第一项\n2. 第二项'} />)
    expect(screen.getByRole('list')).toBeInTheDocument()
    const bold = screen.getByText('重点')
    expect(bold.tagName).toBe('STRONG')
    expect(bold.className).toContain('text-amber-300')
  })

  it('does not color percentages inside inline code', () => {
    render(<MarkdownText content={'数据 `+3.05%`'} />)
    expect(screen.getByText('+3.05%').tagName).toBe('CODE')
  })
})
