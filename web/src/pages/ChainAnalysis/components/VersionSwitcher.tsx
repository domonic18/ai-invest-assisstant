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
          optionLabelProp="text"
          options={successVersions.map((v) => ({
            value: v.id,
            text: `${formatVersionDate(v.createdAt)} · v${v.versionNo}${
              v.versionNo === latestVersionNo ? ' (最新)' : ''
            } · ${v.nodeCount ?? 0} 环节 / ${v.companyCount ?? 0} 标的`,
            label: (
              <div className="flex items-center justify-between gap-2">
                <span>{`${formatVersionDate(v.createdAt)} · v${v.versionNo}${
                  v.versionNo === latestVersionNo ? ' (最新)' : ''
                } · ${v.nodeCount ?? 0} 环节 / ${v.companyCount ?? 0} 标的`}</span>
                <Popconfirm
                  title="删除该版本？"
                  description="图谱节点与公司将一并清除，AI 分析记录保留。"
                  okText="删除"
                  cancelText="取消"
                  okButtonProps={{ danger: true }}
                  onConfirm={(e) => {
                    e?.stopPropagation()
                    onDelete(v.id)
                  }}
                  onPopupClick={(e) => e.stopPropagation()}
                >
                  <Button
                    type="text"
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                    loading={deletingId === v.id}
                    onMouseDown={(e) => e.stopPropagation()}
                    onClick={(e) => e.stopPropagation()}
                  />
                </Popconfirm>
              </div>
            ),
          }))}
        />
        <Button
          icon={<SwapOutlined />}
          onClick={onCompare}
          disabled={successVersions.length < 2}
        >
          版本对比
        </Button>
        {versions.some((v) => v.status === 'failed') && (
          <Tag color="error">存在失败版本</Tag>
        )}
      </Space>
    </div>
  )
}
