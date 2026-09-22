import { ArrowDownOutlined, ArrowUpOutlined, DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import { Button, Input, Popconfirm, Switch, Tree, Typography } from 'antd'
import { useEffect, useState } from 'react'

import type { ApiKbChapterNode } from '@ai-invest/shared'

type EditNode = { key: string; title: string; children: EditNode[] }

function toEditNodes(nodes: ApiKbChapterNode[]): EditNode[] {
  return nodes.map((n) => ({
    key: n.id,
    title: n.title,
    children: toEditNodes(n.children),
  }))
}

function toWire(nodes: EditNode[]): ApiKbChapterNode[] {
  return nodes.map((n) => ({
    id: n.key,
    title: n.title,
    children: toWire(n.children),
  }))
}

function rekey(nodes: EditNode[], prefix = ''): EditNode[] {
  return nodes.map((n, i) => ({
    key: prefix ? `${prefix}.${i + 1}` : String(i + 1),
    title: n.title,
    children: rekey(n.children, prefix ? `${prefix}.${i + 1}` : String(i + 1)),
  }))
}

export interface ChapterTreePanelProps {
  draft: ApiKbChapterNode[] | null
  published: ApiKbChapterNode[] | null
  onPublish: (chapters: ApiKbChapterNode[]) => Promise<unknown>
}

/** 章节树面板：默认浏览态（只读树），有草稿时可切编辑态（改名/增删/上下移，本地 state），发布整棵提交。 */
export function ChapterTreePanel({ draft, published, onPublish }: ChapterTreePanelProps) {
  const [editing, setEditing] = useState(false)
  const [nodes, setNodes] = useState<EditNode[]>(() => toEditNodes(draft ?? []))
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setNodes(toEditNodes(draft ?? []))
  }, [draft])

  const update = (fn: (prev: EditNode[]) => EditNode[]) => setNodes((prev) => fn(prev))

  const rename = (key: string, title: string) =>
    update((prev) =>
      prev.map(function walk(n): EditNode {
        if (n.key === key) return { ...n, title }
        return { ...n, children: n.children.map(walk) }
      })
    )

  const addChild = (key: string) =>
    update((prev) =>
      prev.map(function walk(n): EditNode {
        if (n.key === key)
          return { ...n, children: [...n.children, { key: `${key}-${Date.now()}`, title: '', children: [] }] }
        return { ...n, children: n.children.map(walk) }
      })
    )

  const remove = (key: string) =>
    update(function (prev): EditNode[] {
      const out: EditNode[] = []
      for (const n of prev) {
        if (n.key === key) continue
        out.push({ ...n, children: n.children.filter((c) => c.key !== key) })
      }
      return out
    })

  const move = (key: string, dir: -1 | 1) =>
    update((prev) => {
      const swapSiblings = (list: EditNode[]): EditNode[] | null => {
        const idx = list.findIndex((n) => n.key === key)
        if (idx >= 0) {
          const target = idx + dir
          if (target < 0 || target >= list.length) return null
          const out = [...list]
          ;[out[idx], out[target]] = [out[target], out[idx]]
          return out
        }
        for (let i = 0; i < list.length; i++) {
          const children = swapSiblings(list[i].children)
          if (children)
            return [...list.slice(0, i), { ...list[i], children }, ...list.slice(i + 1)]
        }
        return null
      }
      return swapSiblings(prev) ?? prev
    })

  const hasEmpty = (list: EditNode[]): boolean =>
    list.some((n) => !n.title.trim() || hasEmpty(n.children))

  const renderTitle = (
    node: EditNode,
    depth: number,
    index: number,
    siblingCount: number
  ) => (
    <div className="flex items-center gap-1">
      <Input
        size="small"
        value={node.title}
        placeholder="章节标题"
        onChange={(e) => rename(node.key, e.target.value)}
        style={{ width: Math.min(240, 200 - depth * 20) }}
      />
      {depth < 1 && (
        <Button size="small" type="text" icon={<PlusOutlined />} onClick={() => addChild(node.key)} />
      )}
      <Button
        size="small"
        type="text"
        icon={<ArrowUpOutlined />}
        disabled={index === 0}
        onClick={() => move(node.key, -1)}
      />
      <Button
        size="small"
        type="text"
        icon={<ArrowDownOutlined />}
        disabled={index === siblingCount - 1}
        onClick={() => move(node.key, 1)}
      />
      <Popconfirm title="删除该节点及其子节点？" onConfirm={() => remove(node.key)}>
        <Button size="small" type="text" danger icon={<DeleteOutlined />} />
      </Popconfirm>
    </div>
  )

  if (draft == null && published == null) {
    return (
      <Typography.Text type="secondary">
        抽取任务完成章节推断后，草稿目录会出现在这里。
      </Typography.Text>
    )
  }

  const showEditor = editing && draft != null

  return (
    <div className="space-y-3" data-testid="chapter-tree-panel">
      <div className="flex items-center justify-between">
        <Typography.Text strong>章节目录</Typography.Text>
        {draft != null && (
          <Switch
            size="small"
            checked={editing}
            onChange={setEditing}
            checkedChildren="编辑"
            unCheckedChildren="浏览"
          />
        )}
      </div>
      {showEditor ? (
        <>
          <div className="flex gap-1">
            <Button
              size="small"
              icon={<PlusOutlined />}
              onClick={() => update((prev) => [...prev, { key: `new-${Date.now()}`, title: '', children: [] }])}
            >
              顶层章节
            </Button>
            <Button
              type="primary"
              size="small"
              loading={busy}
              disabled={nodes.length === 0 || hasEmpty(nodes)}
              onClick={async () => {
                setBusy(true)
                try {
                  await onPublish(toWire(rekey(nodes)))
                } finally {
                  setBusy(false)
                }
              }}
            >
              发布
            </Button>
          </div>
          {nodes.map((node, i) => (
            <div key={node.key} className="space-y-1">
              {renderTitle(node, 0, i, nodes.length)}
              <div className="ml-4 space-y-1">
                {node.children.map((child, j) =>
                  renderTitle(child, 1, j, node.children.length)
                )}
              </div>
            </div>
          ))}
          <Typography.Text type="secondary" className="block text-xs">
            编辑仅保存在本地，「发布」后整棵覆盖写入并同步草稿。
          </Typography.Text>
        </>
      ) : (
        <>
          <Tree
            treeData={toEditNodes(draft ?? published ?? [])}
            selectable={false}
            defaultExpandAll
            blockNode
          />
          <Typography.Text type="secondary" className="block text-xs">
            {draft != null
              ? '当前为草稿目录，打开「编辑」可调整结构后发布。'
              : '当前为已发布目录。'}
          </Typography.Text>
        </>
      )}
    </div>
  )
}
