/** 情绪流单条卡片：9:16 封面缩略图（时长角标）+ 博主 + 立场徽标 + 判断摘要/论点/标的 chips + 原视频与转写降级标注。 */

import { MoreOutlined, PlayCircleOutlined } from '@ant-design/icons'
import { Image, Tooltip } from 'antd'
import dayjs from 'dayjs'

import type { ApiSocialFeedItem, ApiSocialTarget } from '@ai-invest/shared'

import { formatRelativeTime } from '@/utils/formatters'

import { StanceBadge } from './StanceBadge'
import { CATEGORY_LABELS, TARGET_TYPE_LABELS } from './labels'

const douyinVideoUrl = (videoId: string) => `https://www.douyin.com/video/${videoId}`

const COVER_FALLBACK =
  'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA5IDE2Ij48cmVjdCB3aWR0aD0iOSIgaGVpZ2h0PSIxNiIgZmlsbD0iIzJhMmEyYSIvPjwvc3ZnPg=='

function formatDuration(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

function TargetChip({ target }: { target: ApiSocialTarget }) {
  const label = TARGET_TYPE_LABELS[target.targetType]
  return (
    <span className="inline-flex items-center rounded bg-white/[0.06] px-1.5 py-0.5 text-xs opacity-80">
      <span className="opacity-60">{label}·</span>
      {target.name}
    </span>
  )
}

/** 9:16 竖版封面缩略图（宽度对齐抖音 web 信息流惯例 ~120px），右下角时长角标；点击打开原视频，无封面时占位。 */
function CoverThumb({ item }: { item: ApiSocialFeedItem }) {
  return (
    <a
      href={douyinVideoUrl(item.videoId)}
      target="_blank"
      rel="noreferrer"
      aria-label={item.title ?? '查看原视频'}
      className="group relative w-[120px] shrink-0 overflow-hidden rounded"
      style={{ aspectRatio: '9 / 16' }}
    >
      {item.coverUrl ? (
        <Image
          src={item.coverUrl}
          alt={item.title ?? item.videoId}
          width="100%"
          height="100%"
          style={{ objectFit: 'cover' }}
          referrerPolicy="no-referrer"
          preview={false}
          fallback={COVER_FALLBACK}
        />
      ) : (
        <div className="flex size-full items-center justify-center bg-white/[0.04]">
          <PlayCircleOutlined className="text-lg opacity-30" />
        </div>
      )}
      {item.durationSeconds !== null && (
        <span className="absolute right-1 bottom-1 rounded bg-black/60 px-1 text-[10px] leading-4 text-white/90">
          {formatDuration(item.durationSeconds)}
        </span>
      )}
    </a>
  )
}

interface SentimentCardProps {
  item: ApiSocialFeedItem
}

export function SentimentCard({ item }: SentimentCardProps) {
  return (
    <div className="flex gap-3 py-3 border-b border-white/5">
      <span className="font-mono text-xs opacity-70 whitespace-nowrap pt-0.5">
        {dayjs(item.publishedAt).format('HH:mm')}
      </span>
      <CoverThumb item={item} />
      <div className="flex-1 min-w-0 space-y-1.5">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium">{item.accountAlias}</span>
          <StanceBadge stance={item.stance} confidence={item.confidence} />
          {item.transcriptMissing && (
            <Tooltip title="音频转写降级：本条判断基于标题与文案">
              <span className="text-xs rounded px-1 py-0.5 bg-amber-500/15 text-amber-400 border border-amber-500/30">
                未转写
              </span>
            </Tooltip>
          )}
          <span className="text-xs opacity-40">
            {CATEGORY_LABELS[item.category] ?? item.category}
          </span>
          <span className="text-xs opacity-40 ml-auto">
            {formatRelativeTime(item.publishedAt)}
          </span>
        </div>

        {item.title && (
          <div className="text-sm font-medium line-clamp-1">{item.title}</div>
        )}
        <div className="text-sm opacity-90">
          <span className="opacity-50">判断：</span>
          {item.summary}
        </div>

        {item.coreArguments.length > 0 && (
          <ul className="space-y-0.5">
            {item.coreArguments.slice(0, 3).map((argument, index) => (
              <li key={index} className="text-xs opacity-60 flex gap-1">
                <MoreOutlined className="rotate-90 mt-0.5" />
                <span className="min-w-0">{argument}</span>
              </li>
            ))}
          </ul>
        )}

        <div className="flex items-center gap-1.5 flex-wrap">
          {item.targets.map((target, index) => (
            <TargetChip key={index} target={target} />
          ))}
        </div>

        <div className="flex items-center gap-3 text-xs opacity-50">
          {item.diggCount !== null && <span>赞 {item.diggCount}</span>}
          {item.commentCount !== null && <span>评 {item.commentCount}</span>}
          <a
            href={douyinVideoUrl(item.videoId)}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 hover:opacity-100"
          >
            <PlayCircleOutlined />
            原视频
          </a>
        </div>
      </div>
    </div>
  )
}
