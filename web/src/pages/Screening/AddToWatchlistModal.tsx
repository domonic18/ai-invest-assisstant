import { useEffect, useState } from 'react'
import { Alert, Button, Input, message, Modal, Select, Space } from 'antd'
import type { WatchlistGroup } from '@ai-invest/shared'

import { batchAddWatchlist } from '@/api/users'
import type { WatchlistBatchImportResult } from '@/api/users'
import { useInvalidateWatchlist, useWatchlistGroups } from '@/hooks/useWatchlistGroups'
import type { StockScreeningRow } from '@/stores/assistant'
import { apiErrorMessage } from '@/utils/errorMessage'

interface AddToWatchlistModalProps {
  open: boolean
  stocks: StockScreeningRow[]
  onClose: () => void
}

export function AddToWatchlistModal({ open, stocks, onClose }: AddToWatchlistModalProps) {
  const invalidate = useInvalidateWatchlist()
  const { data: groups = [] } = useWatchlistGroups()
  const [groupId, setGroupId] = useState<number | undefined>(undefined)
  const [newGroupName, setNewGroupName] = useState('')
  const [importing, setImporting] = useState(false)
  const [result, setResult] = useState<WatchlistBatchImportResult | null>(null)

  useEffect(() => {
    if (open) {
      setGroupId(undefined)
      setNewGroupName('')
      setResult(null)
    }
  }, [open])

  const doImport = async () => {
    setImporting(true)
    try {
      const trimmed = newGroupName.trim()
      const res = await batchAddWatchlist({
        items: stocks.map((stock) => ({ stockCode: stock.stockCode })),
        groupId: trimmed ? undefined : groupId,
        newGroupName: trimmed || undefined,
      })
      invalidate()
      setResult(res)
    } catch (err) {
      message.error(apiErrorMessage(err, '加入自选失败，请重试'))
    } finally {
      setImporting(false)
    }
  }

  return (
    <Modal
      title={`加入自选分组（${stocks.length} 只）`}
      open={open}
      onCancel={onClose}
      width={560}
      footer={
        result ? (
          <Button type="primary" onClick={onClose}>
            完成
          </Button>
        ) : (
          <Space>
            <Button onClick={onClose}>取消</Button>
            <Button type="primary" loading={importing} onClick={doImport}>
              加入
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
      ) : (
        <Space direction="vertical" className="w-full" size="middle">
          <Space.Compact className="w-full">
            <Select
              className="flex-1"
              placeholder="加入已有分组（留空则用默认分组）"
              allowClear
              value={groupId}
              onChange={setGroupId}
              options={(groups as WatchlistGroup[]).map((g) => ({ value: g.id, label: g.name }))}
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
