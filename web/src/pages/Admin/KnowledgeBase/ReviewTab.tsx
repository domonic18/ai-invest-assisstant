import { PlusOutlined, SendOutlined } from '@ant-design/icons'
import {
  Badge,
  Button,
  Input,
  Modal,
  Pagination,
  Radio,
  Select,
  Space,
  Typography,
  message,
} from 'antd'
import { useState } from 'react'

import type { ApiKbChapterNode, ApiKbPointType } from '@ai-invest/shared'

import { useKbSources } from '@/hooks/useAdminKb'
import {
  useApproveKbPoint,
  useKbChapters,
  useKbReviewPoints,
  useMergeKbPoints,
  usePatchKbPoint,
  usePublishKbChapters,
  useRejectKbPoint,
  useCreateKbPoint,
} from '@/hooks/useAdminKb'

import { ChapterTreePanel } from './ChapterTreePanel'
import { PointCard } from './PointCard'

const PAGE_SIZE = 20

const STATUS_FILTERS = [
  { value: 'draft', label: '待审核' },
  { value: 'published', label: '已通过' },
  { value: 'rejected', label: '已驳回' },
] as const

export function ReviewTab({
  sourceId,
  onSourceChange,
}: {
  sourceId: number | null
  onSourceChange: (id: number | null) => void
}) {
  const { data: sources } = useKbSources()
  const [status, setStatus] = useState<string | null>('draft')
  const [page, setPage] = useState(1)
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [creating, setCreating] = useState(false)

  const { data: chapters } = useKbChapters(sourceId)
  const { data: listing, isLoading } = useKbReviewPoints(sourceId, status, page, PAGE_SIZE)

  const publishChapters = usePublishKbChapters(sourceId ?? 0)
  const createPoint = useCreateKbPoint()
  const patchPoint = usePatchKbPoint()
  const approvePoint = useApproveKbPoint()
  const rejectPoint = useRejectKbPoint()
  const mergePoints = useMergeKbPoints()

  const counts = listing?.counts

  const handleMerge = async () => {
    if (!selectedIds.length) return
    const [first, ...rest] = selectedIds
    await mergePoints.mutateAsync({ targetId: first, sourceIds: rest })
    setSelectedIds([])
    message.success('合并完成')
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Select
          value={sourceId ?? undefined}
          onChange={(v) => {
            onSourceChange(v ?? null)
            setSelectedIds([])
            setPage(1)
          }}
          placeholder="选择知识库"
          style={{ width: 280 }}
          options={(sources ?? []).map((s) => ({
            value: s.id,
            label: `${s.name}（${s.sourceType === 'course' ? '课程' : '电子书'}）`,
          }))}
        />
        <Space wrap>
          {STATUS_FILTERS.map((f) => (
            <Badge
              key={f.value}
              count={
                f.value === 'draft'
                  ? counts?.needsReview
                    ? `复核 ${counts.needsReview}`
                    : 0
                  : 0
              }
              size="small"
            >
              <Radio.Button checked={status === f.value} onClick={() => { setStatus(f.value); setPage(1) }}>
                {f.label} {counts ? `(${String(counts[f.value as keyof typeof counts])})` : ''}
              </Radio.Button>
            </Badge>
          ))}
        </Space>
        <Space wrap className="ml-auto">
          <Button icon={<PlusOutlined />} disabled={!sourceId} onClick={() => setCreating(true)}>
            新增卡片
          </Button>
          <Button
            icon={<SendOutlined />}
            disabled={selectedIds.length < 2}
            loading={mergePoints.isPending}
            onClick={handleMerge}
          >
            合并所选（{selectedIds.length}）
          </Button>
        </Space>
      </div>

      {sourceId == null ? (
        <Typography.Text type="secondary">请先选择知识库。</Typography.Text>
      ) : (
        <div className="flex gap-4">
          <div className="w-[260px] shrink-0 rounded-lg border border-white/10 bg-white/[0.03] p-3">
            <ChapterTreePanel
              draft={chapters?.draft ?? null}
              published={chapters?.published ?? null}
              onPublish={async (nodes) => {
                await publishChapters.mutateAsync({ chapters: nodes })
                message.success('章节树已发布')
              }}
            />
          </div>
          <div className="flex-1 space-y-3">
            {listing?.items.map((point) => (
              <PointCard
                key={point.id}
                point={point}
                chapterTree={(chapters?.published ?? chapters?.draft ?? []) as ApiKbChapterNode[]}
                selectable={status === 'draft'}
                selected={selectedIds.includes(point.id)}
                onToggleSelect={(id, checked) =>
                  setSelectedIds((prev) =>
                    checked ? [...prev, id] : prev.filter((x) => x !== id)
                  )
                }
                onApprove={async (id) => {
                  await approvePoint.mutateAsync(id)
                  message.success('已通过')
                }}
                onPatchApprove={async (id, patch) => {
                  await patchPoint.mutateAsync({ pointId: id, data: patch })
                  message.success('修订已保存')
                }}
                onReject={async (id, reason) => {
                  await rejectPoint.mutateAsync({ pointId: id, data: { reason } })
                  message.success('已驳回')
                }}
              />
            ))}
            <Pagination
              current={page}
              pageSize={PAGE_SIZE}
              total={listing?.total ?? 0}
              onChange={setPage}
              showSizeChanger={false}
              hideOnSinglePage
            />
            {!isLoading && (listing?.items.length ?? 0) === 0 && (
              <Typography.Text type="secondary">
                {status === 'draft' ? '暂无待审核草稿。' : '暂无数据。'}
              </Typography.Text>
            )}
          </div>
        </div>
      )}

      <CreatePointModal
        open={creating}
        sourceId={sourceId}
        mediaOptions={(listing?.items ?? []).map((p) => ({
          value: p.mediaId,
          label: p.mediaTitle ?? `素材 #${String(p.mediaId)}`,
        }))}
        onClose={() => setCreating(false)}
        onSubmit={async (payload) => {
          await createPoint.mutateAsync(payload)
          message.success('已创建草稿')
          setCreating(false)
        }}
      />
    </div>
  )
}

type CreatePayload = {
  mediaId: number
  pointType: ApiKbPointType
  title: string
  body: string
}

function CreatePointModal({
  open,
  sourceId,
  mediaOptions,
  onClose,
  onSubmit,
}: {
  open: boolean
  sourceId: number | null
  mediaOptions: { value: number; label: string }[]
  onClose: () => void
  onSubmit: (payload: CreatePayload) => Promise<unknown>
}) {
  const [mediaId, setMediaId] = useState<number | null>(null)
  const [pointType, setPointType] = useState<ApiKbPointType>('concept')
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [busy, setBusy] = useState(false)

  const valid = sourceId != null && mediaId != null && title.trim() && body.trim()

  return (
    <Modal
      title="人工新增知识卡片"
      open={open}
      onCancel={onClose}
      confirmLoading={busy}
      okText="创建草稿"
      okButtonProps={{ disabled: !valid }}
      onOk={async () => {
        if (!valid) return
        setBusy(true)
        try {
          await onSubmit({ mediaId: mediaId as number, pointType, title, body })
        } finally {
          setBusy(false)
        }
      }}
    >
      <div className="space-y-2" data-testid="create-point-modal">
        <Select
          value={mediaId ?? undefined}
          onChange={setMediaId}
          placeholder="选择素材（取当前队列已有素材）"
          style={{ width: '100%' }}
          options={mediaOptions}
        />
        <Select
          value={pointType}
          onChange={setPointType}
          style={{ width: '100%' }}
          options={[
            { value: 'concept', label: '概念' },
            { value: 'theorem', label: '定理' },
            { value: 'method', label: '方法' },
            { value: 'discipline', label: '纪律' },
            { value: 'case', label: '案例' },
          ]}
        />
        <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="标题" />
        <Input.TextArea
          value={body}
          rows={4}
          onChange={(e) => setBody(e.target.value)}
          placeholder="正文"
        />
      </div>
    </Modal>
  )
}
