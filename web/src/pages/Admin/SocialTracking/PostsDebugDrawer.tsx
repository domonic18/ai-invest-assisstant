/** 作品排查抽屉：账号最近 social_post 行的转写/判级链路状态。 */

import { Drawer, Table, Tag, Tooltip, Typography } from 'antd'
import type { ApiSocialAccountAdmin, ApiSocialPostDebug } from '@ai-invest/shared'

import { useSocialAccountPosts } from '@/hooks/useAdminSocial'
import { formatDateTime } from '@/utils/formatters'

import { StanceBadge } from '@/pages/News/components/Sentiment/StanceBadge'

interface PostsDebugDrawerProps {
  account: ApiSocialAccountAdmin | null
  onClose: () => void
}

const columns = [
  {
    title: '发布时间',
    dataIndex: 'publishedAt',
    width: 110,
    render: (v: string) => (
      <span className="whitespace-nowrap text-xs">{formatDateTime(v)}</span>
    ),
  },
  {
    title: '标题',
    dataIndex: 'title',
    ellipsis: true,
    render: (v: string | null, record: ApiSocialPostDebug) => (
      <Tooltip title={`${record.videoId}\n${v ?? '（无标题）'}`}>
        <Typography.Text ellipsis style={{ maxWidth: 240 }}>
          {v || '-'}
        </Typography.Text>
      </Tooltip>
    ),
  },
  {
    title: '转写',
    dataIndex: 'transcriptStatus',
    width: 90,
    render: (v: string, record: ApiSocialPostDebug) =>
      v === 'ok' ? (
        <Tag color="green">已转写</Tag>
      ) : (
        <Tooltip title={record.transcriptReason ?? '未知原因'}>
          <Tag color="orange">降级</Tag>
        </Tooltip>
      ),
  },
  {
    title: '判级',
    key: 'judgment',
    width: 130,
    render: (_: unknown, record: ApiSocialPostDebug) => {
      if (!record.judgedAt) return <Tag>未判</Tag>
      if (record.isRelevant === false) return <Tag>不入流</Tag>
      return (
        <StanceBadge
          stance={record.stance as 'bullish' | 'bearish' | 'neutral'}
          confidence={record.confidence}
        />
      )
    },
  },
]

export function PostsDebugDrawer({ account, onClose }: PostsDebugDrawerProps) {
  const postsQuery = useSocialAccountPosts(account?.id ?? null)
  return (
    <Drawer
      title={account ? `作品排查 · ${account.alias}` : '作品排查'}
      open={account !== null}
      onClose={onClose}
      width={640}
    >
      <Table
        dataSource={postsQuery.data ?? []}
        columns={columns}
        rowKey="videoId"
        size="small"
        loading={postsQuery.isLoading}
        pagination={false}
      />
    </Drawer>
  )
}
