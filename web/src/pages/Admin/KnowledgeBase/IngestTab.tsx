import {
  Button,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { FolderOpenOutlined, FileAddOutlined, ProfileOutlined } from '@ant-design/icons'
import { useMemo, useRef, useState } from 'react'

import type { ApiKbMediaResponse, ApiKbProcessStatus } from '@ai-invest/shared'

import { useConfirmKbCost, useDeleteKbMedia, useEstimateKbCost, useKbSourceMedia, useKbSources, useRequeueKbMedia } from '@/hooks/useAdminKb'
import { formatBytes } from '@/utils/formatters'

import { CostEstimateModal } from './CostEstimateModal'
import { TranscriptEditor } from './TranscriptEditor'
import { UploadQueue } from './UploadQueue'
import { useKbUploadQueue } from './useKbUploadQueue'

const STATUS_META: Record<ApiKbProcessStatus, { label: string; color: string }> = {
  uploaded: { label: '已上传', color: 'default' },
  awaiting_cost: { label: '待确认费用', color: 'gold' },
  queued: { label: '排队中', color: 'cyan' },
  processing: { label: '转写中', color: 'processing' },
  done: { label: '已完成', color: 'success' },
  failed: { label: '失败', color: 'error' },
}

const KIND_LABEL: Record<string, string> = {
  video: '视频',
  audio: '音频',
  book: '电子书',
}

const COST_ELIGIBLE: ApiKbProcessStatus[] = ['uploaded', 'awaiting_cost']

export function IngestTab({
  sourceId,
  onSourceChange,
}: {
  sourceId: number | null
  onSourceChange: (id: number | null) => void
}) {
  const { data: sources } = useKbSources()
  const { data: media = [], isLoading } = useKbSourceMedia(sourceId)
  const uploadQueue = useKbUploadQueue(sourceId)
  const estimateMutation = useEstimateKbCost()
  const confirmCostMutation = useConfirmKbCost()
  const deleteMediaMutation = useDeleteKbMedia()
  const requeueMediaMutation = useRequeueKbMedia()

  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [estimateOpen, setEstimateOpen] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [editingMedia, setEditingMedia] = useState<ApiKbMediaResponse | null>(null)
  const dirInputRef = useRef<HTMLInputElement | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const costEstimate = estimateMutation.data ?? null
  const editableIds = useMemo(
    () => media.filter((m) => COST_ELIGIBLE.includes(m.processStatus)).map((m) => m.id),
    [media]
  )

  const handleFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return
    const count = uploadQueue.start(Array.from(files))
    if (count === 0) message.warning('所选文件没有可识别的音视频/电子书类型')
    if (dirInputRef.current) dirInputRef.current.value = ''
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const openEstimate = async () => {
    if (!sourceId || selectedIds.length === 0) return
    try {
      await estimateMutation.mutateAsync({ sourceId, mediaIds: selectedIds })
      setEstimateOpen(true)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '预估失败')
    }
  }

  const handleConfirmCost = async () => {
    if (!sourceId || !costEstimate) return
    setConfirming(true)
    try {
      const result = await confirmCostMutation.mutateAsync({
        sourceId,
        data: { mediaIds: costEstimate.items.map((it) => it.mediaId) },
      })
      message.success(`已入队 ${result.queuedIds.length} 个素材`)
      setEstimateOpen(false)
      setSelectedIds([])
    } catch (err) {
      message.error(err instanceof Error ? err.message : '确认失败')
    } finally {
      setConfirming(false)
    }
  }

  const handleDeleteMedia = async (row: ApiKbMediaResponse) => {
    try {
      await deleteMediaMutation.mutateAsync(row.id)
      message.success('已删除（24 小时内可恢复）')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败')
    }
  }

  const handleRequeueMedia = async (row: ApiKbMediaResponse) => {
    try {
      await requeueMediaMutation.mutateAsync(row.id)
      message.success('已重新入队，等待转写扫描拾起（已完成分片不重复计费）')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '重新入队失败')
    }
  }

  const columns: ColumnsType<ApiKbMediaResponse> = [
    {
      title: '集号',
      dataIndex: 'episodeNo',
      width: 70,
      render: (v: number | null) => v ?? '-',
    },
    {
      title: '标题',
      dataIndex: 'title',
      ellipsis: true,
      render: (title: string | null, row) => (
        <div>
          <div>{title ?? row.fileName}</div>
          <Typography.Text type="secondary" className="text-xs" ellipsis={{ tooltip: row.relativePath ?? row.fileName }}>
            {row.relativePath ?? row.fileName}
          </Typography.Text>
        </div>
      ),
    },
    {
      title: '类型',
      dataIndex: 'mediaKind',
      width: 80,
      render: (kind: string) => KIND_LABEL[kind] ?? kind,
    },
    {
      title: '时长/页数',
      dataIndex: 'durationSeconds',
      width: 110,
      render: (_: unknown, row) =>
        row.durationSeconds != null
          ? `${Math.floor(row.durationSeconds / 60)}分${row.durationSeconds % 60}秒`
          : row.pageCount != null
            ? `${row.pageCount} 页`
            : '-',
    },
    {
      title: '大小',
      dataIndex: 'fileSize',
      width: 90,
      render: (v: number | null) => (v == null ? '-' : formatBytes(v)),
    },
    {
      title: '状态',
      dataIndex: 'processStatus',
      width: 130,
      render: (status: ApiKbProcessStatus, row) => {
        const meta = STATUS_META[status] ?? { label: status, color: 'default' }
        return (
          <Tooltip title={row.processError ?? undefined}>
            <Tag color={meta.color}>{meta.label}</Tag>
          </Tooltip>
        )
      },
    },
    {
      title: '知识点/待索引',
      width: 120,
      render: (_: unknown, row) => (
        <span>
          {row.pointCount}
          <span className="text-gray-500"> / </span>
          {row.dirtyCount}
        </span>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 180,
      render: (_: unknown, row) => (
        <Space size="small">
          {row.processStatus === 'done' && (
            <Button
              size="small"
              type="link"
              icon={<ProfileOutlined />}
              onClick={() => setEditingMedia(row)}
            >
              文稿
            </Button>
          )}
          {(row.processStatus === 'failed' || row.processStatus === 'processing') && (
            <Button
              size="small"
              type="link"
              disabled={requeueMediaMutation.isPending}
              onClick={() => handleRequeueMedia(row)}
            >
              重新转写
            </Button>
          )}
          <Button
            size="small"
            type="link"
            danger
            disabled={deleteMediaMutation.isPending}
            onClick={() => handleDeleteMedia(row)}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Select
          value={sourceId ?? undefined}
          onChange={(v) => {
            onSourceChange(v ?? null)
            setSelectedIds([])
          }}
          placeholder="选择知识库"
          style={{ width: 280 }}
          options={(sources ?? []).map((s) => ({
            value: s.id,
            label: `${s.name}（${s.sourceType === 'course' ? '课程' : '电子书'}）`,
          }))}
        />
        <Space wrap>
          <Button
            icon={<FolderOpenOutlined />}
            disabled={!sourceId || uploadQueue.running}
            onClick={() => dirInputRef.current?.click()}
          >
            上传目录
          </Button>
          <Button
            icon={<FileAddOutlined />}
            disabled={!sourceId || uploadQueue.running}
            onClick={() => fileInputRef.current?.click()}
          >
            上传文件
          </Button>
        </Space>
        {editableIds.length > 0 && (
          <Typography.Text type="secondary">
            当前 {editableIds.length} 个素材待预估/确认费用
          </Typography.Text>
        )}
      </div>

      {/* webkitdirectory 目录选择：属性由 ref 设置以绕过 TS 属性表 */}
      <input
        ref={(el) => {
          dirInputRef.current = el
          if (el) {
            el.setAttribute('webkitdirectory', '')
            el.setAttribute('directory', '')
          }
        }}
        type="file"
        multiple
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
      <input
        ref={(el) => {
          fileInputRef.current = el
        }}
        type="file"
        multiple
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />

      {sourceId != null && (
        <UploadQueue
          items={uploadQueue.items}
          progress={uploadQueue.progress}
          running={uploadQueue.running}
          onRetry={uploadQueue.retry}
          onClear={uploadQueue.clear}
        />
      )}

      <Table
        size="small"
        rowKey="id"
        columns={columns}
        dataSource={media}
        loading={isLoading}
        pagination={{ pageSize: 20, showSizeChanger: false }}
        rowSelection={{
          selectedRowKeys: selectedIds,
          onChange: (keys) => setSelectedIds(keys as number[]),
          getCheckboxProps: (row) => ({
            disabled: !COST_ELIGIBLE.includes(row.processStatus),
          }),
        }}
        locale={{ emptyText: sourceId == null ? '请先选择知识库' : '暂无素材' }}
      />

      <div className="mt-3">
        <Button
          type="primary"
          disabled={selectedIds.length === 0 || !sourceId}
          loading={estimateMutation.isPending}
          onClick={openEstimate}
        >
          预估费用（{selectedIds.length}）
        </Button>
      </div>

      <CostEstimateModal
        open={estimateOpen}
        loading={estimateMutation.isPending}
        estimate={costEstimate}
        confirming={confirming}
        onCancel={() => setEstimateOpen(false)}
        onConfirm={handleConfirmCost}
      />
      <TranscriptEditor
        sourceId={sourceId ?? 0}
        media={editingMedia}
        open={editingMedia != null}
        onClose={() => setEditingMedia(null)}
      />
    </div>
  )
}
