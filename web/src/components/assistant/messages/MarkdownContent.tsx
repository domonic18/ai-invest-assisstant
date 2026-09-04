import { CheckOutlined, CopyOutlined } from '@ant-design/icons'
import {
  createContext,
  useContext,
  useState,
  type ReactNode,
} from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { useColorScheme } from '@/stores/settings'
import { rehypeRiseFall } from '@/utils/rehypeRiseFall'
import { fallColorSoft, riseColorSoft } from '@/utils/formatters'

interface MarkdownContentProps {
  content: string
}

const CodeBlockContext = createContext(false)

function CodeBlock({ children }: { children: React.ReactNode }) {
  const [copied, setCopied] = useState(false)
  const text = typeof children === 'string' ? children : ''

  const handleCopy = async () => {
    if (!text) return
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // ignore
    }
  }

  return (
    <div className="relative my-2 overflow-hidden rounded-lg border border-gray-700 bg-[#0c0e12]">
      <button
        type="button"
        onClick={handleCopy}
        className="absolute right-2 top-2 rounded p-1 text-xs text-gray-500 transition-colors hover:bg-white/10 hover:text-gray-300"
        title="复制"
      >
        {copied ? <CheckOutlined /> : <CopyOutlined />}
      </button>
      <pre className="max-h-96 overflow-auto p-3 text-xs leading-5 text-gray-300">
        <code>{children}</code>
      </pre>
    </div>
  )
}

function InlineCode({ children }: { children?: ReactNode }) {
  return (
    <code className="rounded bg-amber-400/15 px-1 py-0.5 text-amber-300">
      {String(children ?? '')}
    </code>
  )
}

function CodeComponent({ children }: { children?: ReactNode }) {
  const insideBlock = useContext(CodeBlockContext)
  const text = String(children ?? '')
  return insideBlock ? <CodeBlock>{text}</CodeBlock> : <InlineCode>{text}</InlineCode>
}

function Pre({ children }: { children?: ReactNode }) {
  return (
    <CodeBlockContext.Provider value={true}>
      <div>{children}</div>
    </CodeBlockContext.Provider>
  )
}

/** 助手消息的 Markdown 渲染器：支持表格、列表、代码块、引用、涨跌色。 */
export function MarkdownContent({ content }: MarkdownContentProps) {
  useColorScheme()

  const components = {
    span({ node, children, ...props }: { node?: unknown; children?: ReactNode }) {
      const rf = (node as { properties?: { dataRf?: unknown } } | undefined)
        ?.properties?.dataRf
      if (rf === 'up') {
        return <span className={riseColorSoft()}>{children}</span>
      }
      if (rf === 'down') {
        return <span className={fallColorSoft()}>{children}</span>
      }
      return <span {...props}>{children}</span>
    },
    code: CodeComponent,
    pre: Pre,
    strong({ children }: { children?: ReactNode }) {
      return <strong className="font-semibold text-white">{children}</strong>
    },
    ol({ children }: { children?: ReactNode }) {
      return <ol className="list-decimal space-y-1 pl-5">{children}</ol>
    },
    ul({ children }: { children?: ReactNode }) {
      return <ul className="list-disc space-y-1 pl-5">{children}</ul>
    },
    p({ children }: { children?: ReactNode }) {
      return <p className="leading-6">{children}</p>
    },
    blockquote({ children }: { children?: ReactNode }) {
      return (
        <blockquote className="my-2 border-l-2 border-blue-500/50 bg-blue-500/5 py-1 pl-3 text-gray-300">
          {children}
        </blockquote>
      )
    },
    table({ children }: { children?: ReactNode }) {
      return (
        <div className="my-2 overflow-x-auto">
          <table className="w-full border-collapse text-sm">{children}</table>
        </div>
      )
    },
    thead({ children }: { children?: ReactNode }) {
      return <thead className="bg-gray-800">{children}</thead>
    },
    th({ children }: { children?: ReactNode }) {
      return <th className="border border-gray-700 px-2 py-1 text-left font-medium text-gray-200">{children}</th>
    },
    td({ children }: { children?: ReactNode }) {
      return <td className="border border-gray-700 px-2 py-1 text-gray-300">{children}</td>
    },
    tr({ children }: { children?: ReactNode }) {
      return <tr className="even:bg-white/[0.02]">{children}</tr>
    },
    h1({ children }: { children?: ReactNode }) {
      return <h1 className="my-3 text-lg font-semibold text-white">{children}</h1>
    },
    h2({ children }: { children?: ReactNode }) {
      return <h2 className="my-2 text-base font-semibold text-white">{children}</h2>
    },
    h3({ children }: { children?: ReactNode }) {
      return <h3 className="my-2 text-sm font-semibold text-white">{children}</h3>
    },
    a({ children, href }: { children?: ReactNode; href?: string }) {
      return (
        <a
          href={href}
          target="_blank"
          rel="noreferrer"
          className="text-blue-400 underline underline-offset-2 hover:text-blue-300"
        >
          {children}
        </a>
      )
    },
    hr() {
      return <hr className="my-3 border-gray-700" />
    },
  } as unknown as Components

  return (
    <div className="space-y-2 text-sm text-gray-100">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRiseFall]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
