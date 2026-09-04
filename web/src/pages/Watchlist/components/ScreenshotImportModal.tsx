import { useCallback, useEffect, useMemo, useState } from 'react'
import { InboxOutlined } from '@ant-design/icons'
import {
  Alert,
  Button,
  Input,
  message,
  Modal,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Upload,
} from 'antd'
import type { RcFile } from 'antd/es/upload'
import type { WatchlistGroup } from '@ai-invest/shared'

import {
  batchAddWatchlist,
  recognizeWatchlistScreenshot,
} from '@/api/users'
import type { WatchlistBatchImportResult, WatchlistRecognizedItem } from '@/api/users'
import { useInvalidateWatchlist } from '@/hooks/useWatchlistGroups'

import { apiErrorMessage } from '@/utils/errorMessage'

const MAX_IMAGE_BYTES = 8 * 1024 * 1024
const ALLOWED_IMAGE_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp'])

interface ScreenshotImportModalProps {
  open: boolean
  groups: WatchlistGroup[]
  onClose: () => void
}

type RowStatus = 'duplicated' | 'valid' | 'invalid'

const STATUS_TAG: Record<RowStatus, { color: string; text: string }> = {
  duplicated: { color: 'orange', text: '已在自选' },
  valid: { color: 'green', text: '可导入' },
  invalid: { color: 'default', text: '无法识别' },
}

export function ScreenshotImportModal({ open, groups, onClose }: ScreenshotImportModalProps) {
  const invalidate = useInvalidateWatchlist()
  const [recognizing, setRecognizing] = useState(false)
  const [items, setItems] = useState<WatchlistRecognizedItem[]>([])
  const [selectedCodes, setSelectedCodes] = useState<Set<string>>(new Set())
  const [importing, setImporting] = useState(false)
  const [result, setResult] = useState<WatchlistBatchImportResult | null>(null)
  const [groupId, setGroupId] = useState<number | undefined>(undefined)
  const [newGroupName, setNewGroupName] = useState('')

  const existingCodes = useMemo(
    () => new Set(groups.flatMap((g) => g.items.map((item) => item.code))),
    [groups],
  )

  const statusOf = useCallback(
    (item: WatchlistRecognizedItem): RowStatus => {
      if (!item.valid) return 'invalid'
      if (existingCodes.has(item.stockCode)) return 'duplicated'
      return 'valid'
    },
    [existingCodes],
  )

  const reset = useCallback(() => {
    setRecognizing(false)
    setItems([])
    setSelectedCodes(new Set())
    setImporting(false)
    setResult(null)
    setGroupId(undefined)
    setNewGroupName('')
  }, [])

  const close = () => {
    reset()
    onClose()
  }

  const handleFile = useCallback(
    async (file: File) => {
      if (!ALLOWED_IMAGE_TYPES.has(file.type)) {
        message.warning('仅支持 png/jpeg/webp 图片')
        return
      }
      if (file.size > MAX_IMAGE_BYTES) {
        message.warning('图片超过 8MB 限制')
        return
      }
      setRecognizing(true)
      try {
        const recognized = await recognizeWatchlistScreenshot(file)
        if (!recognized.length) {
          message.info('未从截图中识别到股票')
        }
        setItems(recognized)
        setSelectedCodes(
          new Set(
            recognized
              .filter((item) => item.valid && !existingCodes.has(item.stockCode))
              .map((item) => item.stockCode),
          ),
        )
      } catch (err) {
        message.error(apiErrorMessage(err, '识别失败，请重试'))
      } finally {
        setRecognizing(false)
      }
    },
    [existingCodes],
  )

  useEffect(() => {
    if (!open) return
    const onPaste = (event: ClipboardEvent) => {
      const file = Array.from(event.clipboardData?.files ?? []).find((f) =>
        f.type.startsWith('image/'),
      )
      if (file) void handleFile(file)
    }
    window.addEventListener('paste', onPaste)
    return () => window.removeEventListener('paste', onPaste)
  }, [open, handleFile])

  const importableCount = items.filter(
    (item) => selectedCodes.has(item.stockCode) && statusOf(item) !== 'invalid',
  ).length

  const doImport = async () => {
    const selected = items.filter(
      (item) => selectedCodes.has(item.stockCode) && statusOf(item) !== 'invalid',
    )
    if (!selected.length) return
    setImporting(true)
    try {
      const trimmed = newGroupName.trim()
      const res = await batchAddWatchlist({
        items: selected.map((item) => ({ stock_code: item.stockCode })),
        groupId: trimmed ? undefined : groupId,
        newGroupName: trimmed || undefined,
      })
      invalidate()
      setResult(res)
    } catch (err) {
      message.error(apiErrorMessage(err, '导入失败，请重试'))
    } finally {
      setImporting(false)
    }
  }

  const beforeUpload = (file: RcFile) => {
    void handleFile(file)
    return false
  }

  return (
    <Modal
      title="截图导入自选股"
      open={open}
      onCancel={close}
      width={640}
      footer={
        result ? (
          <Button type="primary" onClick={close}>
            完成
          </Button>
        ) : (
          <Space>
            <Button onClick={close}>取消</Button>
            <Button
              type="primary"
              disabled={importableCount === 0}
              loading={importing}
              onClick={doImport}
            >
              导入选中（{importableCount}）
            </Button>
          </Space>
        )
      }
    >
      {result ? (
        <Alert
          type="success"
          showIcon
          message="导入完成"
          description={`新增 ${result.created} 只，重复跳过 ${result.duplicated.length} 只，无效忽略 ${result.invalid.length} 只。`}
        />
      ) : recognizing ? (
        <div className="flex flex-col items-center gap-3 py-10">
          <Spin />
          <span className="text-sm text-gray-500">AI 正在识别截图中的股票…</span>
        </div>
      ) : items.length === 0 ? (
        <Upload.Dragger
          accept="image/png,image/jpeg,image/webp"
          maxCount={1}
          showUploadList={false}
          beforeUpload={beforeUpload}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">点击上传，或直接 Ctrl/Cmd+V 粘贴截图</p>
          <p className="ant-upload-hint">png/jpeg/webp，≤8MB；也可拖拽图片到此处</p>
        </Upload.Dragger>
      ) : (
        <Space direction="vertical" className="w-full" size="middle">
          <Upload
            accept="image/png,image/jpeg,image/webp"
            maxCount={1}
            showUploadList={false}
            beforeUpload={beforeUpload}
          >
            <Button size="small">重新上传 / 粘贴</Button>
          </Upload>
          <Table
            size="small"
            rowKey="stockCode"
            dataSource={items}
            pagination={false}
            scroll={{ y: 320 }}
            rowSelection={{
              selectedRowKeys: items
                .filter((item) => selectedCodes.has(item.stockCode))
                .map((item) => item.stockCode),
              onChange: (keys) => setSelectedCodes(new Set(keys as string[])),
              getCheckboxProps: (item) => ({ disabled: statusOf(item) === 'invalid' }),
            }}
            columns={[
              { title: '代码', dataIndex: 'stockCode', width: 90 },
              {
                title: '识别名称',
                dataIndex: 'stockName',
                ellipsis: true,
                render: (name: string | null) => name ?? '-',
              },
              {
                title: '校验名称',
                dataIndex: 'matchedName',
                ellipsis: true,
                render: (name: string | null) => name ?? '-',
              },
              {
                title: '置信度',
                dataIndex: 'confidence',
                width: 80,
                render: (value: number | null) =>
                  value != null ? `${Math.round(value * 100)}%` : '-',
              },
              {
                title: '状态',
                key: 'status',
                width: 90,
                render: (_: unknown, item) => {
                  const status = statusOf(item)
                  return <Tag color={STATUS_TAG[status].color}>{STATUS_TAG[status].text}</Tag>
                },
              },
            ]}
          />
          <Space.Compact className="w-full">
            <Select
              className="flex-1"
              placeholder="导入到已有分组（留空则用默认分组）"
              allowClear
              value={groupId}
              onChange={setGroupId}
              options={groups.map((g) => ({ value: g.id, label: g.name }))}
              disabled={newGroupName.trim().length > 0}
            />
            <Input
              className="flex-1"
              placeholder="或新建分组名称"
              maxLength={50}
              value={newGroupName}
              onChange={(e) => setNewGroupName(e.target.value)}
            />
          </Space.Compact>
        </Space>
      )}
    </Modal>
  )
}
