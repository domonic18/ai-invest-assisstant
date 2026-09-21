import { useQuery } from '@tanstack/react-query'
import { Alert, Spin, Typography } from 'antd'
import { useState } from 'react'

import { fetchKbConsumerSources } from '@/api/kb'
import { queryKeys } from '@/hooks/queryKeys'
import { SearchTab } from '@/pages/Admin/KnowledgeBase/SearchTab'

function isForbidden(error: unknown): boolean {
  return (error as { response?: { status?: number } } | null)?.response?.status === 403
}

/** 消费侧知识检索（/kb）：白名单用户入口，403 时页面自解释授权引导。 */
export function KnowledgeSearchPage() {
  const [sourceId, setSourceId] = useState<number | null>(null)
  const { data: sources, isLoading, error } = useQuery({
    queryKey: queryKeys.kb.consumerSources,
    queryFn: fetchKbConsumerSources,
  })

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spin />
      </div>
    )
  }

  if (error != null) {
    if (isForbidden(error)) {
      return (
        <Alert
          type="warning"
          showIcon
          message="暂无知识库访问权限"
          description="请联系管理员在「管理后台 → 知识库 → 设置」中将你加入授权用户后刷新本页。"
        />
      )
    }
    return <Alert type="error" showIcon message="知识库加载失败，请稍后重试" />
  }

  return (
    <div className="flex h-full flex-col gap-4">
      <div>
        <Typography.Title level={4} className="!mb-1">
          知识检索
        </Typography.Title>
        <Typography.Text type="secondary">
          课程与书稿的混合检索：知识卡片、原文摘录与图表，支持定位到原片段与原书页。
        </Typography.Text>
      </div>
      <SearchTab sourceId={sourceId} onSourceChange={setSourceId} consumerSources={sources ?? []} />
    </div>
  )
}
