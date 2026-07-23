import { SwapOutlined } from '@ant-design/icons'
import { Button, Select, Space, Tag, Typography } from 'antd'

import type { ChainVersionSummary } from '@ai-invest/shared'

interface VersionSwitcherProps {
  versions: ChainVersionSummary[]
  currentVersionId: number | null
  onChange: (versionId: number) => void
  onCompare: () => void
}

export function VersionSwitcher({
  versions,
  currentVersionId,
  onChange,
  onCompare,
}: VersionSwitcherProps) {
  const successVersions = versions.filter((v) => v.status === 'success')

  return (
    <Space wrap>
      <Typography.Text type="secondary">版本</Typography.Text>
      <Select
        value={currentVersionId ?? undefined}
        onChange={onChange}
        style={{ minWidth: 260 }}
        options={successVersions.map((v) => ({
          value: v.id,
          label: `v${v.versionNo} · ${new Date(v.createdAt).toLocaleString('zh-CN')} · ${v.nodeCount ?? 0} 环节 / ${v.companyCount ?? 0} 标的`,
        }))}
      />
      {versions.some((v) => v.status === 'failed') && (
        <Tag color="error">存在失败版本</Tag>
      )}
      <Button
        icon={<SwapOutlined />}
        onClick={onCompare}
        disabled={successVersions.length < 2}
      >
        版本对比
      </Button>
    </Space>
  )
}
