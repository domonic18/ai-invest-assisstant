import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import { MarkdownContent } from './MarkdownContent'
import { fallHexSoft, riseHexSoft } from '@/utils/formatters'

// jsdom 将内联 style.color 归一为 rgb() 形式，hex 期望值同构换算后比较
const rgb = (hex: string) => {
  const n = parseInt(hex.slice(1), 16)
  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`
}

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
    // 涨跌色唯一 API 是 hex 系 helper：断言内联 style 与 helper 输出一致
    expect(screen.getByText('+3.05%').style.color).toBe(rgb(riseHexSoft()))
    expect(screen.getByText('-1.20%').style.color).toBe(rgb(fallHexSoft()))
  })

  it('renders ordered and unordered lists', () => {
    const content = `- 第一项
- 第二项

1. 有序`
    render(<MarkdownContent content={content} />)
    const lists = screen.getAllByRole('list')
    expect(lists.length).toBeGreaterThanOrEqual(2)
  })

  it('renders markdown image syntax as inline previewable image', () => {
    render(
      <MarkdownContent content="![K线截图](https://minio.local/kline-drawings/a.png?X-Amz-Signature=1)" />,
    )
    const img = screen.getByRole('img', { name: 'K线截图' })
    expect(img).toHaveAttribute(
      'src',
      'https://minio.local/kline-drawings/a.png?X-Amz-Signature=1',
    )
  })

  it('converts a bare image url link into an inline image', () => {
    // agent 贴裸链接（remark-gfm 自动链接化）时同样内联渲染为图片
    render(
      <MarkdownContent content="[截图](https://minio.local/kline-drawings/a.png?sig=1)" />,
    )
    const img = screen.getByRole('img')
    expect(img).toHaveAttribute('src', 'https://minio.local/kline-drawings/a.png?sig=1')
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  it('keeps non-image links as text links', () => {
    render(<MarkdownContent content="[详情](https://example.com/page)" />)
    const link = screen.getByRole('link', { name: '详情' })
    expect(link).toHaveAttribute('href', 'https://example.com/page')
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })
})
