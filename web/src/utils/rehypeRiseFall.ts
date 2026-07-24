import type { Element, Root, RootContent } from 'hast'

const RISE_FALL_PATTERN = /([+-]\d+(?:\.\d+)?\s*(?:万亿|亿元|亿|万元|万|%))/g

function splitTextNode(value: string): RootContent[] {
  const parts: RootContent[] = []
  let lastIndex = 0
  for (const match of value.matchAll(RISE_FALL_PATTERN)) {
    const token = match[0]
    const index = match.index
    if (index > lastIndex) {
      parts.push({ type: 'text', value: value.slice(lastIndex, index) })
    }
    parts.push({
      type: 'element',
      tagName: 'span',
      properties: { dataRf: token.startsWith('+') ? 'up' : 'down' },
      children: [{ type: 'text', value: token }],
    })
    lastIndex = index + token.length
  }
  if (lastIndex < value.length) {
    parts.push({ type: 'text', value: value.slice(lastIndex) })
  }
  return parts
}

function visit(parent: Root | Element): void {
  const next: RootContent[] = []
  for (const child of parent.children) {
    if (child.type === 'text') {
      next.push(...splitTextNode(child.value))
      continue
    }
    if (
      child.type === 'element' &&
      child.tagName !== 'code' &&
      child.tagName !== 'pre'
    ) {
      visit(child)
    }
    next.push(child)
  }
  parent.children = next
}

/** 把文本中的带符号数字（百分比 +3.05% / 资金金额 +102 亿、-1.2 万亿）包上 data-rf 标记的 span，供组件层按涨跌/流入流出配色。 */
export function rehypeRiseFall() {
  return (tree: Root) => {
    visit(tree)
  }
}
