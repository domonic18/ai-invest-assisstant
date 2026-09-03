import { useEffect, useState } from 'react'

import { Modal, Select, message } from 'antd'

import { useAddWatchlistItem } from '@/hooks/useWatchlist'
import { useWatchlistGroups } from '@/hooks/useWatchlistGroups'

import { apiErrorMessage } from '@/utils/errorMessage'

interface AddToWatchlistModalProps {
  open: boolean
  stockCode: string
  onClose: () => void
}

export function AddToWatchlistModal({ open, stockCode, onClose }: AddToWatchlistModalProps) {
  const { data: groups } = useWatchlistGroups()
  const addMutation = useAddWatchlistItem()
  const [groupId, setGroupId] = useState<number | undefined>(undefined)

  const defaultGroup = groups?.find((g) => g.isDefault)

  useEffect(() => {
    if (open) {
      setGroupId(defaultGroup?.id)
    }
    // 每次打开时重置为默认分组
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, stockCode])

  const handleOk = () => {
    addMutation.mutate(
      { stockCode, tags: [], groupId },
      {
        onSuccess: () => {
          message.success(`已加入自选：${stockCode}`)
          onClose()
        },
        onError: (err) => message.error(apiErrorMessage(err, '加入自选失败')),
      },
    )
  }

  return (
    <Modal
      open={open}
      title="加入自选"
      okText="确定"
      cancelText="取消"
      confirmLoading={addMutation.isPending}
      onOk={handleOk}
      onCancel={onClose}
      width={360}
    >
      <div className="py-2">
        <div className="mb-2 text-sm text-gray-500">选择分组</div>
        <Select<number>
          className="w-full"
          placeholder="默认分组"
          value={groupId}
          loading={!groups}
          onChange={(v) => setGroupId(v)}
          options={(groups ?? []).map((g) => ({
            value: g.id,
            label: g.isDefault ? `${g.name}（默认）` : g.name,
          }))}
        />
      </div>
    </Modal>
  )
}
