import { Button, Progress, Tag, Typography } from 'antd'
import { CloseOutlined, RedoOutlined } from '@ant-design/icons'

import { KB_MULTIPART_THRESHOLD_BYTES } from '@ai-invest/shared'

import type { UploadItem, UploadItemStatus } from './useKbUploadQueue'

const STATUS_META: Record<UploadItemStatus, { label: string; color?: string }> = {
  hashing: { label: '计算哈希', color: 'processing' },
  uploading: { label: '上传中', color: 'processing' },
  confirming: { label: '服务端核对', color: 'processing' },
  done: { label: '完成', color: 'success' },
  skipped: { label: '已跳过', color: 'default' },
  failed: { label: '失败', color: 'error' },
}

function formatSize(bytes: number): string {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} GB`
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${Math.max(1, Math.round(bytes / 1024))} KB`
}

export function UploadQueue({
  items,
  progress,
  running,
  onRetry,
  onClear,
}: {
  items: UploadItem[]
  progress: Record<string, number>
  running: boolean
  onRetry: (uid?: string) => void
  onClear: () => void
}) {
  if (items.length === 0) return null

  const doneCount = items.filter((it) => it.status === 'done').length
  const skippedCount = items.filter((it) => it.status === 'skipped').length
  const failedCount = items.filter((it) => it.status === 'failed').length
  const summary =
    [
      `完成 ${doneCount}`,
      skippedCount > 0 ? `跳过 ${skippedCount}` : null,
      failedCount > 0 ? `失败 ${failedCount}` : null,
    ]
      .filter(Boolean)
      .join(' · ') || '待上传 0'

  return (
    <div className="mb-4 rounded-md border border-white/10 bg-white/[0.03] p-3">
      <div className="mb-2 flex items-center justify-between">
        <Typography.Text type="secondary">
          上传队列 {summary} / {items.length}（直传 COS，完成后服务端核对大小与 md5）
        </Typography.Text>
        <div className="flex items-center gap-2">
          {failedCount > 0 && (
            <Button
              size="small"
              icon={<RedoOutlined />}
              disabled={running}
              onClick={() => onRetry()}
            >
              重试失败项
            </Button>
          )}
          <Button
            size="small"
            icon={<CloseOutlined />}
            disabled={running}
            onClick={onClear}
          >
            清理已完成/已跳过
          </Button>
        </div>
      </div>
      <div className="flex max-h-64 flex-col gap-2 overflow-y-auto">
        {items.map((it) => {
          const meta = STATUS_META[it.status]
          const showError =
            (it.status === 'failed' || it.status === 'skipped') && it.error
          return (
            <div key={it.uid} className="flex items-center gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <Typography.Text ellipsis className="max-w-[420px]" title={it.relativePath}>
                    {it.relativePath}
                  </Typography.Text>
                  <Typography.Text type="secondary" className="shrink-0 text-xs">
                    {formatSize(it.size)}
                  </Typography.Text>
                </div>
                {showError ? (
                  <Typography.Text
                    type={it.status === 'failed' ? 'danger' : 'secondary'}
                    className="text-xs"
                  >
                    {it.error}
                  </Typography.Text>
                ) : it.status === 'skipped' ? null : (
                  <Progress
                    percent={progress[it.uid] ?? 0}
                    size="small"
                    status={it.status === 'done' ? 'success' : 'active'}
                  />
                )}
              </div>
              {it.status === 'failed' && !running && (
                <Typography.Link className="shrink-0 text-xs" onClick={() => onRetry(it.uid)}>
                  {it.size > KB_MULTIPART_THRESHOLD_BYTES ? '续传' : '重试'}
                </Typography.Link>
              )}
              <Tag color={meta.color} className="shrink-0">
                {meta.label}
              </Tag>
            </div>
          )
        })}
      </div>
    </div>
  )
}
