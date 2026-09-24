import { CheckCircleOutlined, EditOutlined, UndoOutlined } from '@ant-design/icons'
import { Button, Checkbox, Input, Popconfirm, Select, Tag, TreeSelect, Typography } from 'antd'
import { useState } from 'react'

import type { ApiKbChapterNode, ApiKbKnowledgePoint } from '@ai-invest/shared'

const POINT_TYPE_OPTIONS = [
  { value: 'concept', label: '概念' },
  { value: 'theorem', label: '定理' },
  { value: 'method', label: '方法' },
  { value: 'discipline', label: '纪律' },
  { value: 'case', label: '案例' },
]

const POINT_TYPE_COLORS: Record<string, string> = {
  concept: 'blue',
  theorem: 'purple',
  method: 'cyan',
  discipline: 'orange',
  case: 'geekblue',
}

const STATUS_TAGS: Record<string, { color: string; label: string }> = {
  draft: { color: 'default', label: '草稿' },
  published: { color: 'success', label: '已通过' },
  rejected: { color: 'error', label: '已驳回' },
}

function fmtMs(ms: number | null): string {
  if (ms == null) return '?'
  const total = Math.floor(ms / 1000)
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}

function toTreeData(nodes: ApiKbChapterNode[]): { value: string; title: string; children: { value: string; title: string }[] }[] {
  return nodes.map((n) => ({
    value: n.title,
    title: n.title,
    children: n.children.map((c) => ({ value: c.title, title: c.title })),
  }))
}

export interface PointCardProps {
  point: ApiKbKnowledgePoint
  chapterTree: ApiKbChapterNode[]
  selectable?: boolean
  selected?: boolean
  onToggleSelect?: (id: number, checked: boolean) => void
  onApprove: (id: number) => Promise<unknown>
  onPatchApprove: (id: number, patch: Record<string, unknown>) => Promise<unknown>
  onReject: (id: number, reason: string | null) => Promise<unknown>
}

/** 知识卡片（审核工作台队列项）：标签/正文/原文脚注 + 通过/修订后通过/驳回。 */
export function PointCard({
  point,
  chapterTree,
  selectable = false,
  selected = false,
  onToggleSelect,
  onApprove,
  onPatchApprove,
  onReject,
}: PointCardProps) {
  const [editing, setEditing] = useState(false)
  const [rejecting, setRejecting] = useState(false)
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState({
    title: point.title,
    pointType: point.pointType,
    body: point.body,
    termDefinition: point.termDefinition ?? '',
    applicableScene: point.applicableScene ?? '',
    chapterPath: point.chapterPath,
  })
  const [reason, setReason] = useState('')

  const statusTag = STATUS_TAGS[point.status] ?? STATUS_TAGS.draft

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true)
    try {
      await fn()
    } finally {
      setBusy(false)
      setEditing(false)
      setRejecting(false)
    }
  }

  return (
    <div data-testid="point-card" className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        {selectable && point.status === 'draft' && (
          <Checkbox
            checked={selected}
            onChange={(e) => onToggleSelect?.(point.id, e.target.checked)}
            aria-label={`选择 ${point.title}`}
          />
        )}
        <Tag color={POINT_TYPE_COLORS[point.pointType] ?? 'default'}>
          {POINT_TYPE_OPTIONS.find((o) => o.value === point.pointType)?.label ?? point.pointType}
        </Tag>
        <Typography.Text strong className="flex-1">{point.title}</Typography.Text>
        <Tag color={statusTag.color}>{statusTag.label}</Tag>
        {point.needsReview && <Tag color="warning">需人工复核</Tag>}
      </div>

      {point.needsReview && point.reviewNote && (
        <Typography.Text type="warning" className="mb-2 block text-xs">
          升级原因：{point.reviewNote}
        </Typography.Text>
      )}

      <Typography.Paragraph className="mb-2 whitespace-pre-wrap">{point.body}</Typography.Paragraph>

      {(point.termDefinition || point.applicableScene) && !editing && (
        <div className="mb-2 space-y-1 text-xs text-white/60">
          {point.termDefinition && <div>释义：{point.termDefinition}</div>}
          {point.applicableScene && <div>适用场景：{point.applicableScene}</div>}
        </div>
      )}

      <div className="mb-3 text-xs text-white/50">
        原文 · {point.mediaTitle ?? '未知素材'}
        {(point.startMs != null || point.endMs != null) &&
          ` ${fmtMs(point.startMs)}–${fmtMs(point.endMs)}`}
        {point.chapterPath.length > 0 && ` · ${point.chapterPath.join(' / ')}`}
      </div>

      {!editing && !rejecting && (
        <div className="flex gap-2">
          {point.status !== 'published' && (
            <Button
              type="primary"
              size="small"
              icon={<CheckCircleOutlined />}
              loading={busy}
              onClick={() => run(() => onApprove(point.id))}
            >
              通过
            </Button>
          )}
          <Button size="small" icon={<EditOutlined />} onClick={() => setEditing(true)}>
            修订后通过
          </Button>
          <Popconfirm
            title="驳回该知识点？"
            open={rejecting}
            onOpenChange={(open) => {
              if (!open) setRejecting(false)
            }}
            description={
              <Input
                placeholder="驳回理由（可选）"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                style={{ width: 220 }}
              />
            }
            onConfirm={() => run(() => onReject(point.id, reason || null))}
          >
            <Button size="small" danger onClick={() => setRejecting(true)}>
              驳回
            </Button>
          </Popconfirm>
        </div>
      )}

      {editing && (
        <div className="space-y-2" data-testid="point-edit-form">
          <Input
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            placeholder="标题"
          />
          <div className="flex gap-2">
            <Select
              value={form.pointType}
              options={POINT_TYPE_OPTIONS}
              onChange={(v) => setForm({ ...form, pointType: v })}
              style={{ width: 120 }}
            />
            <TreeSelect
              value={form.chapterPath}
              treeData={toTreeData(chapterTree)}
              multiple
              treeDefaultExpandAll
              allowClear
              placeholder="归属章节路径"
              style={{ flex: 1 }}
              onChange={(v) => setForm({ ...form, chapterPath: v ?? [] })}
            />
          </div>
          <Input.TextArea
            value={form.body}
            rows={3}
            onChange={(e) => setForm({ ...form, body: e.target.value })}
          />
          <Input
            value={form.termDefinition}
            onChange={(e) => setForm({ ...form, termDefinition: e.target.value })}
            placeholder="术语释义（可选）"
          />
          <Input
            value={form.applicableScene}
            onChange={(e) => setForm({ ...form, applicableScene: e.target.value })}
            placeholder="适用场景（可选）"
          />
          <div className="flex gap-2">
            <Button
              type="primary"
              size="small"
              loading={busy}
              onClick={() =>
                run(async () => {
                  await onPatchApprove(point.id, {
                    title: form.title,
                    pointType: form.pointType,
                    body: form.body,
                    termDefinition: form.termDefinition || null,
                    applicableScene: form.applicableScene || null,
                    chapterPath: form.chapterPath,
                  })
                  await onApprove(point.id)
                })
              }
            >
              保存并通过
            </Button>
            <Button size="small" icon={<UndoOutlined />} onClick={() => setEditing(false)}>
              取消
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
