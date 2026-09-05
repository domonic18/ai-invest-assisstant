import { DeleteOutlined, SwapOutlined } from '@ant-design/icons'
import { Button, Popconfirm, Select, Space, Tag, Typography } from 'antd'

import type { ChainVersionSummary } from '@ai-invest/shared'

interface VersionSwitcherProps {
  versions: ChainVersionSummary[]
  currentVersionId: number | null
  onChange: (versionId: number) => void
  onCompare: () => void
  onDelete: (versionId: number) => void
  deletingId?: number | null
}

function formatVersionDate(iso: string): string {
  const date = new Date(iso)
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const dd = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${mm}-${dd}`
}

function versionText(v: ChainVersionSummary, latestVersionNo: number): string {
  return `${formatVersionDate(v.createdAt)} · v${v.versionNo}${
    v.versionNo === latestVersionNo ? ' (最新)' : ''
  } · ${v.nodeCount ?? 0} 环节 / ${v.companyCount ?? 0} 标的`
}

export function VersionSwitcher({
  versions,
  currentVersionId,
  onChange,
  onCompare,
  onDelete,
  deletingId,
}: VersionSwitcherProps) {
  const successVersions = versions.filter((v) => v.status === 'success')
  const latestVersionNo = Math.max(...successVersions.map((v) => v.versionNo))
  const hasCurrent = currentVersionId != null

  return (
    <div className="flex items-center justify-between gap-3 flex-wrap rounded-lg border border-solid border-[#23262d] bg-[#111318] px-4 py-2">
      <Space wrap>
        <Typography.Text type="secondary" strong>
          图谱版本:
        </Typography.Text>
        <Select
          value={currentVersionId ?? undefined}
          onChange={onChange}
          style={{ minWidth: 280 }}
          popupMatchSelectWidth={false}
          options={successVersions.map((v) => ({
            value: v.id,
            label: versionText(v, latestVersionNo),
          }))}
        />
        <Button
          icon={<SwapOutlined />}
          onClick={onCompare}
          disabled={successVersions.length < 2}
        >
          版本对比
        </Button>
        <Popconfirm
          title="删除当前版本？"
          description="图谱节点与公司将一并清除，AI 分析记录保留。"
          okText="删除"
          cancelText="取消"
          okButtonProps={{ danger: true }}
          disabled={!hasCurrent}
          onConfirm={() => {
            if (currentVersionId != null) onDelete(currentVersionId)
          }}
        >
          <Button
            danger
            icon={<DeleteOutlined />}
            disabled={!hasCurrent}
            loading={hasCurrent && deletingId === currentVersionId}
          >
            删除版本
          </Button>
        </Popconfirm>
        {versions.some((v) => v.status === 'failed') && (
          <Tag color="error">存在失败版本</Tag>
        )}
      </Space>
    </div>
  )
}
