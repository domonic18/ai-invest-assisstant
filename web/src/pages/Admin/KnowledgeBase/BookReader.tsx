import {
  CloseOutlined,
  LeftOutlined,
  RightOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
} from '@ant-design/icons'
import { Button, InputNumber, Segmented, Spin, Typography, message } from 'antd'
import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchKbPlaybackToken, kbBookPageUrl } from '@/api/kb'

import { TOKEN_REFRESH_MARGIN_SECONDS } from './playerUtils'

const PAGE_STORAGE_KEY_PREFIX = 'kb-reader-page:'
const ZOOM_OPTIONS = [
  { value: 1, label: '100%' },
  { value: 1.5, label: '150%' },
  { value: 2, label: '200%' },
]

export interface ReaderHitPage {
  pageNo: number
  label?: string
}

export interface BookReaderProps {
  mediaId: number
  title?: string | null
  /** 初始定位页（检索命中跳页），优先于断点续读页。 */
  initialPageNo?: number | null
  /** 命中页标注（当前页页角标签 + 快捷跳转 chips）。 */
  hitPages?: ReaderHitPage[]
  onClose?: () => void
}

function readSavedPage(mediaId: number): number | null {
  const raw = Number(localStorage.getItem(PAGE_STORAGE_KEY_PREFIX + mediaId))
  return Number.isFinite(raw) && raw >= 1 ? Math.floor(raw) : null
}

export function BookReader({
  mediaId,
  title,
  initialPageNo = null,
  hitPages = [],
  onClose,
}: BookReaderProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  const [token, setToken] = useState<string | null>(null)
  const [pageCount, setPageCount] = useState<number | null>(null)
  // 初始页在首渲染前读定（命中页 > 断点续读页 > 1）：持久化 effect 首拍即回写，
  // 若拖到 token 到达再读 localStorage，保存值已被 page=1 覆盖
  const [page, setPage] = useState(() => {
    const target = initialPageNo ?? readSavedPage(mediaId)
    return target != null ? Math.max(1, Math.floor(target)) : 1
  })
  const [pageLoading, setPageLoading] = useState(true)
  const [zoom, setZoom] = useState(1)

  // ---- 阅读凭证：加载 + 到期前自动刷新（换 token 重指当前页 src） ----
  useEffect(() => {
    let cancelled = false
    let timer: number | undefined
    const load = async () => {
      try {
        const next = await fetchKbPlaybackToken(mediaId)
        if (cancelled) return
        setToken(next.token)
        setPageCount(next.pageCount)
        if (next.pageCount != null) {
          setPage((current) => Math.min(current, next.pageCount ?? current))
        }
        timer = window.setTimeout(
          () => void load(),
          Math.max(30, next.expiresIn - TOKEN_REFRESH_MARGIN_SECONDS) * 1000
        )
      } catch {
        if (!cancelled) void message.error('阅读凭证获取失败，请稍后重试')
      }
    }
    void load()
    return () => {
      cancelled = true
      if (timer != null) window.clearTimeout(timer)
    }
  }, [mediaId])

  // 命中定位页变化（同书再次定位）时跳页
  useEffect(() => {
    if (initialPageNo != null && initialPageNo > 0) setPage(initialPageNo)
  }, [initialPageNo])

  useEffect(() => {
    localStorage.setItem(PAGE_STORAGE_KEY_PREFIX + mediaId, String(page))
  }, [page, mediaId])

  const clampPage = useCallback(
    (next: number) => {
      const upper = pageCount ?? Number.MAX_SAFE_INTEGER
      setPage(Math.min(Math.max(1, Math.floor(next)), upper))
    },
    [pageCount]
  )

  const onKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (event.key === 'ArrowLeft') {
        event.preventDefault()
        clampPage(page - 1)
      } else if (event.key === 'ArrowRight') {
        event.preventDefault()
        clampPage(page + 1)
      }
    },
    [page, clampPage]
  )

  const currentHit = hitPages.find((hit) => hit.pageNo === page)

  return (
    <div
      ref={containerRef}
      tabIndex={0}
      onKeyDown={onKeyDown}
      className="rounded-lg border border-white/10 bg-white/[0.03] p-3 outline-none"
    >
      <div className="mb-2 flex items-center gap-2">
        <Typography.Text strong ellipsis className="flex-1">
          {title ?? `书稿 #${mediaId}`}
        </Typography.Text>
        <Typography.Text type="secondary" className="text-xs tabular-nums">
          {pageCount != null ? `第 ${page} / ${pageCount} 页` : `第 ${page} 页`}
        </Typography.Text>
        {onClose && (
          <Button size="small" type="text" icon={<CloseOutlined />} onClick={onClose} />
        )}
      </div>

      <div className="mb-2 flex flex-wrap items-center gap-2">
        <Button
          size="small"
          icon={<LeftOutlined />}
          disabled={page <= 1}
          onClick={() => clampPage(page - 1)}
        >
          上一页
        </Button>
        <InputNumber
          size="small"
          min={1}
          max={pageCount ?? undefined}
          value={page}
          onChange={(value) => value != null && clampPage(value)}
          className="w-20"
        />
        <Button
          size="small"
          disabled={pageCount != null && page >= pageCount}
          onClick={() => clampPage(page + 1)}
        >
          下一页
          <RightOutlined />
        </Button>
        <Segmented
          size="small"
          value={zoom}
          options={ZOOM_OPTIONS}
          onChange={(value) => setZoom(value as number)}
        />
        <Button
          size="small"
          type="text"
          icon={<ZoomOutOutlined />}
          onClick={() => setZoom((z) => Math.max(1, Number((z - 0.5).toFixed(1))))}
        />
        <Button
          size="small"
          type="text"
          icon={<ZoomInOutlined />}
          onClick={() => setZoom((z) => Math.min(3, Number((z + 0.5).toFixed(1))))}
        />
        {hitPages.length > 0 && (
          <div className="ml-auto flex flex-wrap items-center gap-1">
            <Typography.Text type="secondary" className="text-xs">
              命中页：
            </Typography.Text>
            {hitPages.map((hit) => (
              <Button
                key={hit.pageNo}
                size="small"
                type={hit.pageNo === page ? 'primary' : 'default'}
                ghost={hit.pageNo === page}
                className="!h-6 !px-2 !text-xs"
                onClick={() => clampPage(hit.pageNo)}
              >
                第 {hit.pageNo} 页
              </Button>
            ))}
          </div>
        )}
      </div>

      {/* 书页位图：服务端水印烧录；禁拖拽/右键抬高转存门槛 */}
      <div className="relative flex max-h-[70vh] justify-center overflow-auto rounded bg-black/40">
        {!token ? (
          <Spin className="self-center" />
        ) : (
          <div className="relative" style={{ width: `${zoom * 100}%` }}>
            {pageLoading && (
              <div className="absolute inset-0 z-10 flex items-center justify-center">
                <Spin />
              </div>
            )}
            <img
              key={`${page}-${token}`}
              src={kbBookPageUrl(mediaId, page, token)}
              alt={`第 ${page} 页`}
              draggable={false}
              onContextMenu={(e) => e.preventDefault()}
              onLoad={() => setPageLoading(false)}
              onError={() => {
                setPageLoading(false)
                void message.error('书页加载失败：凭证可能已过期，正在自动刷新重试')
              }}
              className="w-full"
            />
            {currentHit && (
              <div className="pointer-events-none absolute right-2 top-2 rounded bg-amber-400/80 px-2 py-0.5 text-xs text-black/80">
                命中 · {currentHit.label ?? ''}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
