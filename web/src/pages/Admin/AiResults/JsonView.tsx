import { DownOutlined, RightOutlined } from '@ant-design/icons'
import { useState } from 'react'

interface JsonNodeProps {
  name?: string
  value: unknown
  depth: number
}

function isExpandable(value: unknown): value is Record<string, unknown> | unknown[] {
  return typeof value === 'object' && value !== null
}

function formatPrimitive(value: unknown): string {
  if (value === null) return 'null'
  if (typeof value === 'string') return value
  return String(value)
}

function JsonNode({ name, value, depth }: JsonNodeProps) {
  // 浅层默认展开、深层默认收起，规则驱动以适配任意 skill 的输出结构
  const [open, setOpen] = useState(depth < 2)

  if (!isExpandable(value)) {
    return (
      <div className="py-0.5">
        {name !== undefined && <span className="text-sky-300">{name}: </span>}
        <span className="whitespace-pre-wrap break-all text-gray-200">
          {formatPrimitive(value)}
        </span>
      </div>
    )
  }

  const entries: [string, unknown][] = Array.isArray(value)
    ? value.map((item, index) => [String(index), item])
    : Object.entries(value)

  return (
    <div className="py-0.5">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-1 text-left"
      >
        {open ? (
          <DownOutlined className="text-[10px] text-gray-500" />
        ) : (
          <RightOutlined className="text-[10px] text-gray-500" />
        )}
        {name !== undefined && <span className="text-sky-300">{name}</span>}
        <span className="text-gray-500">
          {Array.isArray(value) ? `[${entries.length}]` : `{${entries.length}}`}
        </span>
      </button>
      {open && (
        <div className="ml-2 border-l border-sky-900/40 pl-3">
          {entries.map(([key, item]) => (
            <JsonNode key={key} name={key} value={item} depth={depth + 1} />
          ))}
          {entries.length === 0 && <div className="py-0.5 text-gray-500">空</div>}
        </div>
      )}
    </div>
  )
}

/** 递归可折叠 JSON 树：结构化输出的通用查看器（规则驱动，无任何 skill 硬编码）。 */
export function JsonView({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="font-mono text-xs">
      {Object.entries(data).map(([key, value]) => (
        <JsonNode key={key} name={key} value={value} depth={0} />
      ))}
    </div>
  )
}
