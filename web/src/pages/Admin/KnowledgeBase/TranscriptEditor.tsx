import { Alert, Drawer, Empty, Input, Space, Spin, Typography, message } from 'antd'
import { useEffect, useMemo, useState } from 'react'

import type { ApiKbMediaResponse } from '@ai-invest/shared'
import dayjs from 'dayjs'

import { useKbTranscript, useSaveKbTranscript } from '@/hooks/useAdminKb'

interface DraftRow {
  seqNo: number
  text: string
  startMs: number | null
  endMs: number | null
  pageStart: number | null
  pageEnd: number | null
}

function fmtMs(ms: number | null): string {
  if (ms == null) return ''
  const total = Math.floor(ms / 1000)
  const mm = String(Math.floor(total / 60)).padStart(2, '0')
  const ss = String(total % 60).padStart(2, '0')
  return `${mm}:${ss}`
}

/**
 * 文稿编辑器（质量最后防线）：按 seqNo 覆盖分段文本；
 * 仅变化分段由后端置脏并更新 edited_at（索引增量拾取）。
 */
export function TranscriptEditor({
  sourceId,
  media,
  open,
  onClose,
}: {
  sourceId: number
  media: ApiKbMediaResponse | null
  open: boolean
  onClose: () => void
}) {
  const mediaId = media?.id ?? null
  const { data, isLoading } = useKbTranscript(open ? sourceId : null, mediaId)
  const saveMutation = useSaveKbTranscript(sourceId)
  const [draft, setDraft] = useState<DraftRow[]>([])

  useEffect(() => {
    if (data) {
      setDraft(data.segments.map((s) => ({ ...s })))
    }
  }, [data])

  const changedCount = useMemo(() => {
    if (!data) return 0
    const original = new Map(data.segments.map((s) => [s.seqNo, s.text]))
    return draft.filter((row) => original.get(row.seqNo) !== row.text).length
  }, [draft, data])

  const handleSave = async () => {
    if (!mediaId) return
    try {
      const result = await saveMutation.mutateAsync({
        mediaId,
        data: { segments: draft.map((r) => ({ seqNo: r.seqNo, text: r.text })) },
      })
      message.success(
        result.updatedCount > 0
          ? `已保存 ${result.updatedCount} 处修改，待重新索引`
          : '文稿无变化'
      )
    } catch (err) {
      message.error(err instanceof Error ? err.message : '保存失败')
    }
  }

  return (
    <Drawer
      title={media ? `文稿编辑 · ${media.title ?? media.fileName}` : '文稿编辑'}
      open={open}
      onClose={onClose}
      width={720}
      extra={
        <Space>
          <Typography.Text type="secondary">
            {changedCount > 0 ? `${changedCount} 处待保存` : ''}
          </Typography.Text>
          <Typography.Text type="secondary">
            {data?.editedAt ? `上次编辑 ${dayjs(data.editedAt).format('YYYY-MM-DD HH:mm')}` : ''}
          </Typography.Text>
          <Typography.Link onClick={handleSave} className={changedCount === 0 ? 'pointer-events-none opacity-50' : ''}>
            保存
          </Typography.Link>
        </Space>
      }
    >
      {isLoading ? (
        <Spin />
      ) : draft.length === 0 ? (
        <Empty description="该素材暂无文稿（转写完成后开放编辑）" />
      ) : (
        <>
          <Alert
            type="info"
            showIcon
            className="mb-3"
            message="保存后仅修改过的分段会重新生成向量索引；时间轴保持不变。"
          />
          <div className="flex flex-col gap-3">
            {draft.map((row) => (
              <div key={row.seqNo} className="flex gap-3">
                <div className="w-16 shrink-0 pt-1 text-right">
                  <Typography.Text type="secondary" className="text-xs">
                    #{row.seqNo}
                  </Typography.Text>
                  <div className="text-xs text-gray-500">
                    {row.startMs != null
                      ? fmtMs(row.startMs)
                      : row.pageStart != null
                        ? `P${row.pageStart}`
                        : ''}
                  </div>
                </div>
                <Input.TextArea
                  value={row.text}
                  autoSize={{ minRows: 1, maxRows: 6 }}
                  onChange={(e) =>
                    setDraft((prev) =>
                      prev.map((r) =>
                        r.seqNo === row.seqNo ? { ...r, text: e.target.value } : r
                      )
                    )
                  }
                />
              </div>
            ))}
          </div>
        </>
      )}
    </Drawer>
  )
}
