import type { Element, Root, Text } from 'hast'
import { describe, expect, it } from 'vitest'

import { rehypeRiseFall } from './rehypeRiseFall'

function renderText(value: string): Root {
  const tree: Root = {
    type: 'root',
    children: [
      {
        type: 'element',
        tagName: 'p',
        properties: {},
        children: [{ type: 'text', value }],
      },
    ],
  }
  rehypeRiseFall()(tree)
  return tree
}

function markedSpans(tree: Root): { value: string; rf: unknown }[] {
  const paragraph = tree.children[0] as Element
  return paragraph.children
    .filter(
      (child): child is Element =>
        child.type === 'element' && child.tagName === 'span',
    )
    .map((span) => ({
      value: (span.children[0] as Text).value,
      rf: span.properties?.dataRf,
    }))
}

describe('rehypeRiseFall', () => {
  it('marks signed percentages as up/down', () => {
    const spans = markedSpans(renderText('沪指 +1.20%，创业板 -0.85%'))
    expect(spans).toEqual([
      { value: '+1.20%', rf: 'up' },
      { value: '-0.85%', rf: 'down' },
    ])
  })

  it('marks signed fund amounts with units', () => {
    const spans = markedSpans(
      renderText('半导体 +102 亿，银行 -45 亿元，全市场 +1.2 万亿，个股 -300 万'),
    )
    expect(spans).toEqual([
      { value: '+102 亿', rf: 'up' },
      { value: '-45 亿元', rf: 'down' },
      { value: '+1.2 万亿', rf: 'up' },
      { value: '-300 万', rf: 'down' },
    ])
  })

  it('ignores unsigned numbers and bare signs', () => {
    const spans = markedSpans(renderText('成交额 1.8 万亿，上涨 3000 家 - 下跌'))
    expect(spans).toEqual([])
  })

  it('does not mark text inside code elements', () => {
    const tree: Root = {
      type: 'root',
      children: [
        {
          type: 'element',
          tagName: 'code',
          properties: {},
          children: [{ type: 'text', value: '+1.20%' }],
        },
      ],
    }
    rehypeRiseFall()(tree)
    const code = tree.children[0] as Element
    expect(code.children).toHaveLength(1)
    expect(code.children[0].type).toBe('text')
  })
})
