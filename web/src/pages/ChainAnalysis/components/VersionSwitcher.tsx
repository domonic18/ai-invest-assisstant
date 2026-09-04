import { SwapOutlined } from '@ant-design/icons'
import { Button, Select, Space, Tag, Typography } from 'antd'

import type { ChainVersionSummary } from '@ai-invest/shared'

interface VersionSwitcherProps {
  versions: ChainVersionSummary[]
  currentVersionId: number | null
  onChange: (versionId: number) => void
  onCompare: () => void
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
          style={{ minWidth: 240 }}
          options={successVersions.map((v) => ({
            value: v.id,
            label: `${formatVersionDate(v.createdAt)} · v${v.versionNo}${
              v.versionNo === latestVersionNo ? ' (最新)' : ''
            } · ${v.nodeCount ?? 0} 环节 / ${v.companyCount ?? 0} 标的`,
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
