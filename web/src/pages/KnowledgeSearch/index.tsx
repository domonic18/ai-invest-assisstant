import { BookOutlined } from '@ant-design/icons'
import { Alert, Input, Modal, Spin, Typography } from 'antd'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { SuggestedChips } from '@/components/assistant/ui/SuggestedChips'
import { fetchKbPlaybackToken } from '@/api/kb'
import { BookReader } from '@/pages/Admin/KnowledgeBase/BookReader'
import { KnowledgePlayer } from '@/pages/Admin/KnowledgeBase/KnowledgePlayer'
import { useAssistantStore } from '@/stores/assistant'

/** 常问知识点（静态精选；点击即触发侧边栏 Agent 检索知识库）。 */
const SUGGESTED_QUESTIONS = [
  '均线金叉的买入纪律',
  '缠论中枢的定义',
  '止损与仓位管理方法',
  '量价关系怎么解读',
  '趋势反转的确认信号',
  '主升浪的识别方法',
  '左侧交易与右侧交易',
  '复盘应该关注哪些维度',
]

type PlaybackPermission = 'checking' | 'allowed' | 'forbidden' | 'error'

interface PlaybackTarget {
  mediaId: number
  kind: string
  seekMs: number | null
  pageNo: number | null
  title: string | null
  episodeNo: number | null
}

function readPlaybackTarget(params: URLSearchParams): PlaybackTarget | null {
  const mediaId = Number(params.get('mediaId'))
  if (!Number.isFinite(mediaId) || mediaId <= 0) return null
  return {
    mediaId,
    kind: params.get('kind') ?? 'video',
    seekMs: params.get('seekMs') != null ? Number(params.get('seekMs')) : null,
    pageNo: params.get('pageNo') != null ? Number(params.get('pageNo')) : null,
    title: params.get('title'),
    episodeNo: params.get('episodeNo') != null ? Number(params.get('episodeNo')) : null,
  }
}

function isForbidden(error: unknown): boolean {
  return (error as { response?: { status?: number } } | null)?.response?.status === 403
}

/** 知识库搜索入口（搜索引擎式）：搜索/建议 chip 触发侧边栏 Agent 检索；
 * 会话内引用 chip 跳转 ?mediaId=… 承载播放（凭证白名单校验，403 自解释）。 */
export function KnowledgeSearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [permission, setPermission] = useState<PlaybackPermission>('checking')
  const target = readPlaybackTarget(searchParams)
  const mediaIdParam = searchParams.get('mediaId')

  useEffect(() => {
    if (mediaIdParam == null) return
    let cancelled = false
    setPermission('checking')
    fetchKbPlaybackToken(Number(mediaIdParam))
      .then(() => {
        if (!cancelled) setPermission('allowed')
      })
      .catch((error: unknown) => {
        if (cancelled) return
        setPermission(isForbidden(error) ? 'forbidden' : 'error')
      })
    return () => {
      cancelled = true
    }
  }, [mediaIdParam])

  const ask = (question: string) => {
    const q = question.trim()
    if (!q) return
    useAssistantStore.getState().sendQuestion(`请在知识库中检索并回答：${q}`)
  }

  const closePlayback = () => setSearchParams({}, { replace: true })

  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 px-4">
      <div className="flex flex-col items-center gap-2">
        <BookOutlined className="text-4xl text-blue-400" />
        <Typography.Title level={3} className="!mb-0">
          知识库
        </Typography.Title>
        <Typography.Text type="secondary">
          检索投资课程与书稿知识卡片，由 AI 助手检索引用原文作答
        </Typography.Text>
      </div>
      <Input.Search
        size="large"
        placeholder="输入知识点，如「均线金叉的买入纪律」"
        style={{ maxWidth: 560, width: '100%' }}
        enterButton="搜索"
        onSearch={ask}
        allowClear
      />
      <div className="w-full max-w-[560px]">
        <SuggestedChips questions={SUGGESTED_QUESTIONS} onSelect={ask} centered />
      </div>

      <Modal
        open={target != null}
        onCancel={closePlayback}
        footer={null}
        width={target?.kind === 'book' ? 720 : 960}
        title={
          target?.title ??
          (target?.kind === 'book' ? '书稿阅读' : '课程回放')
        }
        destroyOnClose
      >
        {target == null ? null : permission === 'checking' ? (
          <div className="flex h-72 items-center justify-center">
            <Spin />
          </div>
        ) : permission === 'forbidden' ? (
          <Alert
            type="warning"
            showIcon
            message="暂无知识库播放权限"
            description="原片播放需管理员在「管理后台 → 知识库 → 设置」中将你加入授权用户。"
          />
        ) : permission === 'error' ? (
          <Alert
            type="error"
            showIcon
            message="播放凭证获取失败，请稍后重试"
          />
        ) : target.kind === 'book' ? (
          <BookReader
            key={target.mediaId}
            mediaId={target.mediaId}
            title={target.title}
            initialPageNo={target.pageNo}
          />
        ) : (
          <KnowledgePlayer
            key={target.mediaId}
            mediaId={target.mediaId}
            mediaKind={target.kind === 'audio' ? 'audio' : 'video'}
            title={target.title}
            episodeNo={target.episodeNo}
            initialSeekMs={target.seekMs}
          />
        )}
      </Modal>
    </div>
  )
}
