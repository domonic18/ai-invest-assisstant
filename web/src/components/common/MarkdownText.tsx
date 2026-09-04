import ReactMarkdown, { type Components } from 'react-markdown'

import { useColorScheme } from '@/stores/settings'
import { rehypeRiseFall } from '@/utils/rehypeRiseFall'
import { fallColorSoft, riseColorSoft } from '@/utils/formatters'

interface MarkdownTextProps {
  content: string
  className?: string
}

/** 渲染 AI 复盘 Markdown：`` 高亮重点、带符号百分比按涨跌配色（跟随全站配色方案）。 */
export function MarkdownText({ content, className }: MarkdownTextProps) {
  useColorScheme()

  const components: Components = {
    span({ node, children, ...props }) {
      const rf = node?.properties?.dataRf
      if (rf === 'up') {
        return <span className={riseColorSoft()}>{children}</span>
      }
      if (rf === 'down') {
        return <span className={fallColorSoft()}>{children}</span>
      }
      return <span {...props}>{children}</span>
    },
    code({ children }) {
      return (
        <code className="rounded bg-amber-400/15 px-1 py-0.5 text-amber-300">
          {children}
        </code>
      )
    },
    strong({ children }) {
      return <strong className="font-semibold text-white">{children}</strong>
    },
    ol({ children }) {
      return <ol className="list-decimal space-y-1 pl-5">{children}</ol>
    },
    ul({ children }) {
      return <ul className="list-disc space-y-1 pl-5">{children}</ul>
    },
    p({ children }) {
      return <p className="leading-6">{children}</p>
    },
  }

  return (
    <div className={`space-y-2 ${className ?? ''}`}>
      <ReactMarkdown rehypePlugins={[rehypeRiseFall]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  )
}
