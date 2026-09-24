import { PlayCircleOutlined, ReadOutlined, SearchOutlined } from '@ant-design/icons'
import {
  Alert,
  Button,
  Card,
  Empty,
  Input,
  Modal,
  Segmented,
  Select,
  Space,
  Tag,
  Tooltip,
  Tree,
  Typography,
  message,
} from 'antd'
import type { DataNode } from 'antd/es/tree'
import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import type {
  ApiKbChapterNode,
  ApiKbSearchImageHit,
  ApiKbSearchPointHit,
  ApiKbSearchResponse,
  ApiKbSearchSegmentHit,
} from '@ai-invest/shared'

import { fetchKbImageOriginalUrl } from '@/api/kb'
import { useKbSources } from '@/hooks/useAdminKb'
import { useKbPublishedChapters, useKbSearch } from '@/hooks/useKbSearch'

import { BookReader, type ReaderHitPage } from './BookReader'
import { KnowledgePlayer, type PlayerHitInterval } from './KnowledgePlayer'

const POINT_TYPE_LABELS: Record<string, string> = {
  concept: '概念',
  theorem: '定理',
  method: '方法',
  discipline: '纪律',
  case: '案例',
}

const POINT_TYPE_COLORS: Record<string, string> = {
  concept: 'blue',
  theorem: 'purple',
  method: 'cyan',
  discipline: 'orange',
  case: 'geekblue',
}

const KIND_FILTERS = [
  { value: '全部', label: '全部' },
  { value: 'point', label: '卡片' },
  { value: 'segment', label: '原文' },
  { value: 'image', label: '图片' },
]

interface Submitted {
  q: string
  sourceId: number | null
  chapterPath: string[]
  kind: string | null
}

function pad(n: number): string {
  return String(n).padStart(2, '0')
}

function fmtClock(ms: number | null): string {
  if (ms == null) return '?'
  const s = Math.floor(ms / 1000)
  const h = Math.floor(s / 3600)
  return h > 0 ? `${h}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}` : `${pad(Math.floor(s / 60))}:${pad(s % 60)}`
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function highlight(text: string, terms: string[]): ReactNode {
  const pattern = terms.map(escapeRegExp).filter(Boolean).join('|')
  if (!pattern) return text
  const lowered = terms.map((t) => t.toLowerCase())
  return text
    .split(new RegExp(`(${pattern})`, 'gi'))
    .map((part, i) =>
      lowered.includes(part.toLowerCase()) ? (
        <mark key={i} className="rounded bg-amber-400/30 px-0.5 text-inherit">
          {part}
        </mark>
      ) : (
        part
      )
    )
}

function pointPosition(hit: ApiKbSearchPointHit): string {
  if (hit.mediaKind === 'book') {
    const start = hit.pageStart ?? '?'
    const end = hit.pageEnd ?? hit.pageStart
    return end != null && end !== start ? `第 ${start}–${end} 页` : `第 ${start} 页`
  }
  return `第 ${hit.episodeNo ?? '?'} 集 ${fmtClock(hit.startMs)}–${fmtClock(hit.endMs)}`
}

function buildTree(
  nodes: ApiKbChapterNode[],
  parentPath: string[],
  keyToPath: Map<string, string[]>
): DataNode[] {
  return nodes.map((node) => {
    const path = [...parentPath, node.title]
    keyToPath.set(node.id, path)
    return {
      key: node.id,
      title: node.title,
      children: buildTree(node.children, path, keyToPath),
    }
  })
}

function PointHitCard({
  hit,
  terms,
  onLocate,
}: {
  hit: ApiKbSearchPointHit
  terms: string[]
  onLocate?: (hit: ApiKbSearchPointHit) => void
}) {
  return (
    <Card size="small" className="border-white/10 bg-white/[0.03]">
      <div className="flex flex-wrap items-center gap-2">
        <Tag color={POINT_TYPE_COLORS[hit.pointType] ?? 'default'}>
          {POINT_TYPE_LABELS[hit.pointType] ?? hit.pointType}
        </Tag>
        <Typography.Text strong>{highlight(hit.title, terms)}</Typography.Text>
        {hit.chapterPath.length > 0 && (
          <Typography.Text type="secondary" className="text-xs">
            {hit.chapterPath.join(' / ')}
          </Typography.Text>
        )}
        <span className="ml-auto text-xs text-[#8a8f98]">RRF {hit.score.toFixed(4)}</span>
      </div>
      <Typography.Paragraph ellipsis={{ rows: 2, expandable: true, symbol: '展开' }} className="mt-2 mb-2">
        {highlight(hit.body, terms)}
      </Typography.Paragraph>
      {hit.termDefinition && (
        <Typography.Paragraph className="mb-2 text-xs" type="secondary">
          术语：{highlight(hit.termDefinition, terms)}
        </Typography.Paragraph>
      )}
      <div className="rounded border border-white/10 bg-white/[0.03] px-2 py-1.5">
        <Typography.Text type="secondary" className="text-xs">
          原文摘录：
        </Typography.Text>
        <Typography.Paragraph className="!mb-0 mt-1 text-xs">
          {highlight(hit.excerpt, terms)}
        </Typography.Paragraph>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <Typography.Text type="secondary" className="text-xs">
          {pointPosition(hit)}
          {hit.mediaTitle ? ` · ${hit.mediaTitle}` : ''}
        </Typography.Text>
        {onLocate && (
          <Button
            size="small"
            type="primary"
            ghost
            icon={hit.mediaKind === 'book' ? <ReadOutlined /> : <PlayCircleOutlined />}
            onClick={() => onLocate(hit)}
          >
            {hit.mediaKind === 'book' ? '阅读定位' : '播放定位'}
          </Button>
        )}
        {hit.frames.length > 0 && (
          <div className="ml-auto flex gap-1.5">
            {hit.frames.map((frame) => (
              <Tooltip
                key={frame.id}
                title={`${frame.caption ?? ''} · ${fmtClock(frame.startMs)}`}
              >
                {frame.thumbUrl ? (
                  <img
                    src={frame.thumbUrl}
                    alt={frame.caption ?? ''}
                    className="h-14 w-24 rounded border border-white/10 object-cover"
                  />
                ) : (
                  <span className="text-xs text-[#8a8f98]">无缩略图</span>
                )}
              </Tooltip>
            ))}
          </div>
        )}
      </div>
    </Card>
  )
}

function SegmentHitRow({
  hit,
  terms,
  onLocate,
}: {
  hit: ApiKbSearchSegmentHit
  terms: string[]
  onLocate?: (hit: ApiKbSearchSegmentHit) => void
}) {
  return (
    <div className="rounded border border-white/10 bg-white/[0.03] px-3 py-2">
      <div className="mb-1 flex items-center gap-2">
        <Tag color="default">原文</Tag>
        <Typography.Text type="secondary" className="text-xs">
          第 {hit.episodeNo ?? '?'} 集 {fmtClock(hit.startMs)}–{fmtClock(hit.endMs)}
          {hit.mediaTitle ? ` · ${hit.mediaTitle}` : ''}
        </Typography.Text>
        {onLocate && (
          <Button
            size="small"
            type="primary"
            ghost
            icon={<PlayCircleOutlined />}
            onClick={() => onLocate(hit)}
          >
            播放片段
          </Button>
        )}
        <span className="ml-auto text-xs text-[#8a8f98]">RRF {hit.score.toFixed(4)}</span>
      </div>
      <Typography.Paragraph className="!mb-0 text-xs">
        {highlight(hit.text, terms)}
      </Typography.Paragraph>
    </div>
  )
}

function ImageHitCard({
  hit,
  terms,
  onLocate,
  onViewOriginal,
}: {
  hit: ApiKbSearchImageHit
  terms: string[]
  onLocate?: (hit: ApiKbSearchImageHit) => void
  onViewOriginal?: (hit: ApiKbSearchImageHit) => void
}) {
  const position =
    hit.mediaKind === 'book'
      ? `第 ${hit.pageNo ?? '?'} 页`
      : `第 ${hit.episodeNo ?? '?'} 集 ${fmtClock(hit.startMs)}`
  return (
    <Card
      size="small"
      className="overflow-hidden border-white/10"
      cover={
        <div className="flex h-32 items-center justify-center overflow-hidden bg-black/30">
          {hit.thumbUrl ? (
            <img
              src={hit.thumbUrl}
              alt={hit.caption ?? ''}
              className="max-h-full max-w-full object-contain"
            />
          ) : (
            <Typography.Text type="secondary">无缩略图</Typography.Text>
          )}
        </div>
      }
    >
      <Typography.Paragraph ellipsis={{ rows: 2 }} className="!mb-1 text-xs">
        {highlight(hit.caption ?? hit.textInImage ?? '（无图注）', terms)}
      </Typography.Paragraph>
      <div className="flex items-center justify-between">
        <Typography.Text type="secondary" className="text-xs">
          {position}
        </Typography.Text>
        <Space size={4}>
          {onLocate && (
            <Button
              size="small"
              type="link"
              className="!p-0 !text-xs"
              icon={hit.mediaKind === 'book' ? <ReadOutlined /> : <PlayCircleOutlined />}
              onClick={() => onLocate(hit)}
            >
              {hit.mediaKind === 'book' ? '阅读此页' : '播放帧'}
            </Button>
          )}
          {onViewOriginal && (
            <Button
              size="small"
              type="link"
              className="!p-0 !text-xs"
              onClick={() => onViewOriginal(hit)}
            >
              原图
            </Button>
          )}
        </Space>
      </div>
    </Card>
  )
}

interface PlayerLaunch {
  mediaId: number
  mediaKind: 'video' | 'audio'
  title: string | null
  episodeNo: number | null
  initialSeekMs: number | null
  hitIntervals: PlayerHitInterval[]
}

interface ReaderLaunch {
  mediaId: number
  title: string | null
  initialPageNo: number | null
  hitPages: ReaderHitPage[]
}

/** 聚合当前结果里同素材的视频/音频命中区间（卡片 + 原文分段），供进度条高亮。 */
function buildIntervalsFor(result: ApiKbSearchResponse, mediaId: number): PlayerHitInterval[] {
  const intervals: PlayerHitInterval[] = []
  for (const point of result.points) {
    if (point.mediaId === mediaId && point.mediaKind !== 'book' && point.startMs != null) {
      intervals.push({ startMs: point.startMs, endMs: point.endMs ?? point.startMs, label: point.title })
    }
  }
  for (const segment of result.segments) {
    if (segment.mediaId === mediaId && segment.startMs != null) {
      intervals.push({ startMs: segment.startMs, endMs: segment.endMs ?? segment.startMs })
    }
  }
  return intervals.sort((a, b) => a.startMs - b.startMs)
}

/** 聚合同书命中页（卡片 pageStart + 书嵌图 pageNo），Map 去重保先到标签。 */
function buildPagesFor(result: ApiKbSearchResponse, mediaId: number): ReaderHitPage[] {
  const byPage = new Map<number, ReaderHitPage>()
  for (const point of result.points) {
    if (point.mediaId === mediaId && point.mediaKind === 'book' && point.pageStart != null) {
      byPage.set(point.pageStart, { pageNo: point.pageStart, label: point.title })
    }
  }
  for (const image of result.images) {
    if (
      image.mediaId === mediaId &&
      image.mediaKind === 'book' &&
      image.pageNo != null &&
      !byPage.has(image.pageNo)
    ) {
      byPage.set(image.pageNo, { pageNo: image.pageNo })
    }
  }
  return [...byPage.values()].sort((a, b) => a.pageNo - b.pageNo)
}

export function SearchTab({
  sourceId,
  onSourceChange,
}: {
  sourceId: number | null
  onSourceChange: (id: number | null) => void
}) {
  const { data: sources } = useKbSources()
  const [input, setInput] = useState('')
  const [kind, setKind] = useState<string | null>(null)
  const [selectedChapter, setSelectedChapter] = useState<string[]>([])
  const [submitted, setSubmitted] = useState<Submitted | null>(null)

  const { data: chaptersData } = useKbPublishedChapters(sourceId)
  const { data: result, isLoading } = useKbSearch(submitted)

  const [player, setPlayer] = useState<PlayerLaunch | null>(null)
  const [reader, setReader] = useState<ReaderLaunch | null>(null)
  const [original, setOriginal] = useState<{ url: string; caption: string | null } | null>(null)

  const { treeData, keyToPath } = useMemo(() => {
    const map = new Map<string, string[]>()
    const data = buildTree(chaptersData?.chapters ?? [], [], map)
    return { treeData: data, keyToPath: map }
  }, [chaptersData])

  useEffect(() => {
    setSelectedChapter([])
  }, [sourceId])

  useEffect(() => {
    setSubmitted((prev) =>
      prev ? { ...prev, sourceId, chapterPath: selectedChapter, kind } : prev
    )
  }, [sourceId, selectedChapter, kind])

  const terms = useMemo(
    () => (submitted ? submitted.q.split(/\s+/).filter(Boolean) : []),
    [submitted]
  )

  const submit = () => {
    const q = input.trim()
    if (!q) return
    setSubmitted({ q, sourceId, chapterPath: selectedChapter, kind })
  }

  const openPlayer = (
    mediaId: number,
    mediaKind: 'video' | 'audio',
    title: string | null,
    episodeNo: number | null,
    seekMs: number | null
  ) => {
    if (!result) return
    setReader(null)
    setPlayer({
      mediaId,
      mediaKind,
      title,
      episodeNo,
      initialSeekMs: seekMs,
      hitIntervals: buildIntervalsFor(result, mediaId),
    })
  }

  const openReader = (mediaId: number, title: string | null, pageNo: number | null) => {
    if (!result) return
    setPlayer(null)
    setReader({
      mediaId,
      title,
      initialPageNo: pageNo,
      hitPages: buildPagesFor(result, mediaId),
    })
  }

  const locatePoint = (hit: ApiKbSearchPointHit) => {
    if (hit.mediaKind === 'book') {
      openReader(hit.mediaId, hit.mediaTitle, hit.pageStart)
    } else {
      openPlayer(
        hit.mediaId,
        hit.mediaKind === 'audio' ? 'audio' : 'video',
        hit.mediaTitle,
        hit.episodeNo,
        hit.startMs != null ? Math.max(0, hit.startMs - 4000) : null
      )
    }
  }

  const locateSegment = (hit: ApiKbSearchSegmentHit) => {
    openPlayer(
      hit.mediaId,
      hit.mediaKind === 'audio' ? 'audio' : 'video',
      hit.mediaTitle,
      hit.episodeNo,
      hit.seekMs
    )
  }

  const locateImage = (hit: ApiKbSearchImageHit) => {
    if (hit.mediaKind === 'book') {
      openReader(hit.mediaId, null, hit.pageNo)
    } else {
      openPlayer(hit.mediaId, 'video', null, hit.episodeNo, hit.startMs)
    }
  }

  const viewOriginal = async (hit: ApiKbSearchImageHit) => {
    try {
      const res = await fetchKbImageOriginalUrl(hit.id)
      setOriginal({ url: res.url, caption: hit.caption ?? hit.textInImage ?? null })
    } catch {
      void message.error('原图获取失败，请稍后重试')
    }
  }

  const showPoints = kind !== 'segment' && kind !== 'image'
  const showSegments = kind !== 'point' && kind !== 'image'
  const showImages = kind !== 'point' && kind !== 'segment'
  const hasHits =
    (result?.points.length ?? 0) + (result?.segments.length ?? 0) + (result?.images.length ?? 0) > 0

  return (
    <div className="flex gap-4">
      <Card size="small" className="w-64 shrink-0 self-start" title="章节导航">
        {treeData.length > 0 ? (
          <Tree
            blockNode
            defaultExpandAll
            selectedKeys={selectedChapter.length ? [findKey(keyToPath, selectedChapter)] : []}
            onSelect={(keys) => {
              const key = keys[0]
              if (key == null || key === '') {
                setSelectedChapter([])
              } else {
                setSelectedChapter(keyToPath.get(String(key)) ?? [])
              }
            }}
            treeData={treeData}
          />
        ) : (
          <Typography.Text type="secondary" className="text-xs">
            {sourceId == null ? '请先选择知识库' : '暂无发布态章节树'}
          </Typography.Text>
        )}
      </Card>

      <div className="min-w-0 flex-1">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <Select
            value={sourceId ?? undefined}
            onChange={(v) => onSourceChange(v ?? null)}
            placeholder="选择知识库"
            style={{ width: 240 }}
            options={(sources ?? []).map((s) => ({
              value: s.id,
              label: `${s.name}（${s.sourceType === 'course' ? '课程' : '电子书'}）`,
            }))}
          />
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={submit}
            placeholder="搜索知识点 / 原文 / 图片描述"
            style={{ width: 320 }}
            allowClear
          />
          <Button type="primary" icon={<SearchOutlined />} loading={isLoading} onClick={submit}>
            检索
          </Button>
          <Segmented
            value={kind ?? '全部'}
            options={KIND_FILTERS}
            onChange={(v) => setKind(v === '全部' ? null : String(v))}
          />
          {selectedChapter.length > 0 && (
            <Tag closable onClose={() => setSelectedChapter([])}>
              {selectedChapter.join(' / ')}
            </Tag>
          )}
        </div>

        {result?.degraded === 'embedding_unavailable' && (
          <Alert
            className="mb-4"
            type="info"
            showIcon
            message="向量通道暂不可用，已降级为关键词检索"
          />
        )}

        {player && (
          <div className="mb-4">
            <KnowledgePlayer
              key={player.mediaId}
              mediaId={player.mediaId}
              mediaKind={player.mediaKind}
              title={player.title}
              episodeNo={player.episodeNo}
              hitIntervals={player.hitIntervals}
              initialSeekMs={player.initialSeekMs}
              onClose={() => setPlayer(null)}
            />
          </div>
        )}
        {reader && (
          <div className="mb-4">
            <BookReader
              key={reader.mediaId}
              mediaId={reader.mediaId}
              title={reader.title}
              initialPageNo={reader.initialPageNo}
              hitPages={reader.hitPages}
              onClose={() => setReader(null)}
            />
          </div>
        )}

        {!result ? (
          <Empty description="输入关键词开始混合检索（关键词 + 向量双路召回）" />
        ) : !hasHits && !result.degraded ? (
          <Empty description={`「${result.query}」未找到命中`} />
        ) : (
          <Space direction="vertical" size={16} className="w-full">
            {showPoints && result.points.length > 0 && (
              <section>
                <Typography.Title level={5} className="!mb-2">
                  知识卡片 <Typography.Text type="secondary">({result.points.length})</Typography.Text>
                </Typography.Title>
                <Space direction="vertical" size={8} className="w-full">
                  {result.points.map((hit) => (
                    <PointHitCard key={hit.id} hit={hit} terms={terms} onLocate={locatePoint} />
                  ))}
                </Space>
              </section>
            )}
            {showSegments && result.segments.length > 0 && (
              <section>
                <Typography.Title level={5} className="!mb-2">
                  原文摘录 <Typography.Text type="secondary">({result.segments.length})</Typography.Text>
                </Typography.Title>
                <Space direction="vertical" size={8} className="w-full">
                  {result.segments.map((hit) => (
                    <SegmentHitRow key={hit.id} hit={hit} terms={terms} onLocate={locateSegment} />
                  ))}
                </Space>
              </section>
            )}
            {showImages && result.images.length > 0 && (
              <section>
                <Typography.Title level={5} className="!mb-2">
                  图片 <Typography.Text type="secondary">({result.images.length})</Typography.Text>
                </Typography.Title>
                <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
                  {result.images.map((hit) => (
                    <ImageHitCard
                      key={hit.id}
                      hit={hit}
                      terms={terms}
                      onLocate={locateImage}
                      onViewOriginal={() => void viewOriginal(hit)}
                    />
                  ))}
                </div>
              </section>
            )}
          </Space>
        )}
      </div>

      <Modal
        open={original != null}
        title={original?.caption ?? '原图'}
        footer={null}
        width={960}
        onCancel={() => setOriginal(null)}
      >
        {original && (
          <img
            src={original.url}
            alt={original.caption ?? ''}
            draggable={false}
            onContextMenu={(e) => e.preventDefault()}
            className="max-h-[75vh] w-full select-none object-contain"
          />
        )}
      </Modal>
    </div>
  )
}

function findKey(map: Map<string, string[]>, path: string[]): string {
  for (const [key, value] of map.entries()) {
    if (value.join('\u0000') === path.join('\u0000')) return key
  }
  return ''
}
