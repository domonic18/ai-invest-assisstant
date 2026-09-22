import { PlayCircleOutlined, ReadOutlined } from '@ant-design/icons'
import { Button, Tooltip } from 'antd'
import { useNavigate } from 'react-router-dom'

import { useAssistantStore } from '@/stores/assistant'

/** 知识库工具结果（snake_case 原始载荷）中的结构化媒体引用。 */
interface KbMediaRef {
  id: number
  kind: string
  title?: string
  episodeNo?: number
  seekMs?: number
  pageNo?: number
}

const MAX_CHIPS = 8

function fmtTimecode(ms: number): string {
  const total = Math.floor(ms / 1000)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const mm = String(m).padStart(2, '0')
  const ss = String(s).padStart(2, '0')
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`
}

function chipLabel(ref: KbMediaRef): string {
  if (ref.kind === 'book') return `第${ref.pageNo}页`
  const timecode = ref.seekMs != null ? ` ${fmtTimecode(ref.seekMs)}` : ''
  return ref.episodeNo != null ? `第${ref.episodeNo}集${timecode}` : `${ref.title ?? ''}${timecode}`
}

function toMediaRef(media: Record<string, unknown>): KbMediaRef | null {
  const id = Number(media.id)
  const kind = String(media.kind ?? '')
  if (!Number.isFinite(id) || id <= 0 || !kind) return null
  const ref: KbMediaRef = { id, kind }
  if (typeof media.title === 'string' && media.title) ref.title = media.title
  if (media.episode_no != null) ref.episodeNo = Number(media.episode_no)
  if (media.seek_ms != null) ref.seekMs = Number(media.seek_ms)
  if (media.page_no != null) ref.pageNo = Number(media.page_no)
  if (ref.seekMs == null && ref.pageNo == null) return null
  return ref
}

function collectMediaRefs(result: unknown): KbMediaRef[] {
  // 工具结果经 ToolMessage 传递时是 JSON 字符串（langchain 对 dict 返回值
  // json.dumps），对象与字符串两种形状都接受
  let payload = result
  if (typeof payload === 'string') {
    try {
      payload = JSON.parse(payload)
    } catch {
      return []
    }
  }
  if (typeof payload !== 'object' || payload === null) return []
  const { points, segments } = payload as Record<string, unknown>
  const cards = [...(Array.isArray(points) ? points : []), ...(Array.isArray(segments) ? segments : [])]
  const seen = new Set<string>()
  const refs: KbMediaRef[] = []
  for (const card of cards) {
    if (typeof card !== 'object' || card === null) continue
    const media = (card as Record<string, unknown>).media
    if (typeof media !== 'object' || media === null) continue
    const ref = toMediaRef(media as Record<string, unknown>)
    if (!ref) continue
    const key = `${ref.id}:${ref.seekMs ?? ref.pageNo}`
    if (seen.has(key)) continue
    seen.add(key)
    refs.push(ref)
    if (refs.length >= MAX_CHIPS) break
  }
  return refs
}

/** search_knowledge_base 工具结果的媒体引用 chips：点击收起侧边栏并跳 /kb 播放。 */
export function KbMediaChips({ result }: { result: unknown }) {
  const navigate = useNavigate()
  const refs = collectMediaRefs(result)
  if (refs.length === 0) return null

  const open = (ref: KbMediaRef) => {
    const params = new URLSearchParams({ mediaId: String(ref.id), kind: ref.kind })
    if (ref.seekMs != null) params.set('seekMs', String(ref.seekMs))
    if (ref.pageNo != null) params.set('pageNo', String(ref.pageNo))
    if (ref.title) params.set('title', ref.title)
    if (ref.episodeNo != null) params.set('episodeNo', String(ref.episodeNo))
    useAssistantStore.getState().closePanel()
    navigate(`/kb?${params.toString()}`)
  }

  return (
    <div className="flex flex-wrap items-center gap-1 border-t border-sky-900/40 px-3 py-2">
      <span className="text-xs text-gray-500">原片：</span>
      {refs.map((ref) => (
        <Tooltip key={`${ref.id}:${ref.seekMs ?? ref.pageNo}`} title={ref.title ?? undefined}>
          <Button
            size="small"
            icon={ref.kind === 'book' ? <ReadOutlined /> : <PlayCircleOutlined />}
            onClick={() => open(ref)}
          >
            {chipLabel(ref)}
          </Button>
        </Tooltip>
      ))}
    </div>
  )
}
