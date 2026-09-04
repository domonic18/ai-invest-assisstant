import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import { MarkdownContent } from './MarkdownContent'

describe('MarkdownContent', () => {
  it('renders inline code with amber style', () => {
    render(<MarkdownContent content="市盈率 `PE` 是常用指标" />)
    const code = screen.getByText('PE')
    expect(code.tagName).toBe('CODE')
    expect(code.className).toContain('bg-amber-400/15')
  })

  it('renders a code block with copy button', () => {
    const content = '```\nconst x = 1\n```'
    render(<MarkdownContent content={content} />)
    expect(screen.getByText('const x = 1')).toBeInTheDocument()
    expect(screen.getByTitle('复制')).toBeInTheDocument()
  })

  it('renders a table with headers and cells', () => {
    const content = `| 指标 | 值 |
| ---- | -- |
| 营收 | 100 |`
    render(<MarkdownContent content={content} />)
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getByText('指标')).toBeInTheDocument()
    expect(screen.getByText('营收')).toBeInTheDocument()
  })

  it('colors signed percentages by cn scheme', () => {
    render(<MarkdownContent content="沪指 +3.05% 创业板 -1.20%" />)
    expect(screen.getByText('+3.05%').className).toContain('text-red-')
    expect(screen.getByText('-1.20%').className).toContain('text-green-')
  })

  it('renders ordered and unordered lists', () => {
    const content = `- 第一项
- 第二项

1. 有序`
    render(<MarkdownContent content={content} />)
    const lists = screen.getAllByRole('list')
    expect(lists.length).toBeGreaterThanOrEqual(2)
  })
})
