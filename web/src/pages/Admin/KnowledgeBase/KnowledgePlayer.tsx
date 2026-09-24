import {
  CloseOutlined,
  FullscreenOutlined,
  PauseOutlined,
  PlayCircleOutlined,
  StepBackwardOutlined,
  StepForwardOutlined,
} from '@ant-design/icons'
import { Button, Select, Slider, Spin, Tooltip, Typography, message } from 'antd'
import dayjs from 'dayjs'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  fetchKbPlaybackToken,
  fetchKbSubtitles,
  kbStreamUrl,
} from '@/api/kb'
import { useAuthStore } from '@/stores/auth'

import { fmtClock, parseVttCues, TOKEN_REFRESH_MARGIN_SECONDS, type VttCue } from './playerUtils'

const RATE_OPTIONS = [0.5, 0.75, 1, 1.25, 1.5, 2]
const RATE_STORAGE_KEY = 'kb-player-rate'
const POSITION_KEY_PREFIX = 'kb-player-pos:'
const SEEK_STEP_SECONDS = 5
const POSITION_SAVE_INTERVAL_MS = 5000

export interface PlayerHitInterval {
  startMs: number
  endMs: number
  label?: string
}

function readSavedRate(): number {
  const saved = Number(localStorage.getItem(RATE_STORAGE_KEY))
  return RATE_OPTIONS.includes(saved) ? saved : 1
}

function readSavedPosition(mediaId: number): number | null {
  const raw = localStorage.getItem(POSITION_KEY_PREFIX + mediaId)
  const saved = raw == null ? null : Number(raw)
  return saved != null && Number.isFinite(saved) && saved > 3 ? saved : null
}

interface KnowledgePlayerProps {
  mediaId: number
  mediaKind?: 'video' | 'audio'
  title?: string | null
  episodeNo?: number | null
  /** 命中区间高亮（检索/卡片定位，毫秒闭区间） */
  hitIntervals?: PlayerHitInterval[]
  /** 初始起播点（前滚后 seekMs），优先于断点续播 */
  initialSeekMs?: number | null
  onClose?: () => void
  /** 上/下一集切换（父层持 mediaId 状态并重挂载播放器） */
  onEpisodeChange?: (mediaId: number) => void
}

export function KnowledgePlayer({
  mediaId,
  mediaKind = 'video',
  title,
  episodeNo,
  hitIntervals = [],
  initialSeekMs = null,
  onClose,
  onEpisodeChange,
}: KnowledgePlayerProps) {
  const username = useAuthStore((s) => s.user?.username ?? null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const activeCueRef = useRef<HTMLDivElement>(null)
  /** loadedmetadata 后待应用的起播点（秒；token 刷新续播也走这里） */
  const pendingSeekRef = useRef<number | null>(null)
  const wasPlayingRef = useRef(false)
  const lastSaveRef = useRef(0)
  const refreshedRef = useRef(false)

  const [token, setToken] = useState<string | null>(null)
  const [prevMediaId, setPrevMediaId] = useState<number | null>(null)
  const [nextMediaId, setNextMediaId] = useState<number | null>(null)
  const [cues, setCues] = useState<VttCue[]>([])
  const [playing, setPlaying] = useState(false)
  const [currentMs, setCurrentMs] = useState(0)
  const [durationMs, setDurationMs] = useState(0)
  const [rate, setRate] = useState(readSavedRate)
  const [volume, setVolume] = useState(1)

  // ---- 播放凭证：加载 + 到期前自动刷新（单集可超 30min，防中途 401） ----
  useEffect(() => {
    let cancelled = false
    let timer: number | undefined
    const load = async () => {
      try {
        const next = await fetchKbPlaybackToken(mediaId)
        if (cancelled) return
        const video = videoRef.current
        // 刷新时保住进度与播放态，换 src 后续播
        if (video != null && refreshedRef.current) {
          pendingSeekRef.current = video.currentTime
          wasPlayingRef.current = !video.paused
        }
        refreshedRef.current = true
        setToken(next.token)
        setPrevMediaId(next.prevMediaId)
        setNextMediaId(next.nextMediaId)
        timer = window.setTimeout(
          () => void load(),
          Math.max(30, next.expiresIn - TOKEN_REFRESH_MARGIN_SECONDS) * 1000
        )
      } catch {
        if (!cancelled) void message.error('播放凭证获取失败，请稍后重试')
      }
    }
    void load()
    return () => {
      cancelled = true
      if (timer != null) window.clearTimeout(timer)
    }
  }, [mediaId])

  // ---- 字幕轨 ----
  useEffect(() => {
    let cancelled = false
    setCues([])
    fetchKbSubtitles(mediaId)
      .then((vtt) => {
        if (!cancelled) setCues(parseVttCues(vtt))
      })
      .catch(() => {
        // 字幕是增强层：无文稿/失败静默降级为纯播放
      })
    return () => {
      cancelled = true
    }
  }, [mediaId])

  // ---- src 装载（token 变化重指，loadedmetadata 后恢复进度） ----
  useEffect(() => {
    const video = videoRef.current
    if (!video || !token) return
    video.src = kbStreamUrl(mediaId, token)
    video.load()
    if (pendingSeekRef.current == null) {
      pendingSeekRef.current =
        initialSeekMs != null && initialSeekMs > 0
          ? initialSeekMs / 1000
          : readSavedPosition(mediaId)
    }
  }, [token, mediaId, initialSeekMs])

  // load()/换 src 会把 playbackRate 重置为 1，token 刷新后须重挂倍速
  useEffect(() => {
    const video = videoRef.current
    if (video) video.playbackRate = rate
  }, [rate, token])

  const savePosition = useCallback(() => {
    const video = videoRef.current
    if (video == null || !Number.isFinite(video.currentTime) || video.currentTime <= 0) return
    localStorage.setItem(POSITION_KEY_PREFIX + mediaId, String(video.currentTime))
  }, [mediaId])

  useEffect(() => savePosition, [savePosition, mediaId])

  const activeCueIndex = useMemo(() => {
    if (cues.length === 0) return -1
    for (let i = cues.length - 1; i >= 0; i--) {
      if (currentMs >= cues[i].startMs) return currentMs <= cues[i].endMs ? i : -1
    }
    return -1
  }, [cues, currentMs])

  useEffect(() => {
    activeCueRef.current?.scrollIntoView({ block: 'nearest' })
  }, [activeCueIndex])

  const seekTo = useCallback((seconds: number) => {
    const video = videoRef.current
    if (!video || !Number.isFinite(video.duration) || video.duration <= 0) return
    video.currentTime = Math.min(Math.max(0, seconds), video.duration - 0.2)
  }, [])

  const togglePlay = useCallback(() => {
    const video = videoRef.current
    if (!video) return
    if (video.paused) void video.play()
    else video.pause()
  }, [])

  const onKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      const video = videoRef.current
      if (!video) return
      switch (event.key) {
        case ' ':
        case 'k':
          event.preventDefault()
          togglePlay()
          break
        case 'ArrowLeft':
          event.preventDefault()
          seekTo(video.currentTime - SEEK_STEP_SECONDS)
          break
        case 'ArrowRight':
          event.preventDefault()
          seekTo(video.currentTime + SEEK_STEP_SECONDS)
          break
        case 'ArrowUp':
          event.preventDefault()
          setVolume((v) => Math.min(1, Number((v + 0.1).toFixed(2))))
          break
        case 'ArrowDown':
          event.preventDefault()
          setVolume((v) => Math.max(0, Number((v - 0.1).toFixed(2))))
          break
        default:
          break
      }
    },
    [seekTo, togglePlay]
  )

  useEffect(() => {
    const video = videoRef.current
    if (video) video.volume = volume
  }, [volume])

  const progressRatio = durationMs > 0 ? currentMs / durationMs : 0
  const todayLabel = dayjs().format('YYYY-MM-DD')

  const handleLoadedMetadata = () => {
    const video = videoRef.current
    if (!video) return
    setDurationMs(Number.isFinite(video.duration) ? video.duration * 1000 : 0)
    const pending = pendingSeekRef.current
    pendingSeekRef.current = null
    if (pending != null && Number.isFinite(video.duration) && pending < video.duration - 1) {
      video.currentTime = pending
      setCurrentMs(pending * 1000)
    }
    if (wasPlayingRef.current) {
      wasPlayingRef.current = false
      void video.play()
    }
  }

  const handleTimeUpdate = () => {
    const video = videoRef.current
    if (!video) return
    setCurrentMs(video.currentTime * 1000)
    const now = Date.now()
    if (now - lastSaveRef.current >= POSITION_SAVE_INTERVAL_MS) {
      lastSaveRef.current = now
      savePosition()
    }
  }

  return (
    <div
      ref={containerRef}
      tabIndex={0}
      onKeyDown={onKeyDown}
      className="rounded-lg border border-white/10 bg-white/[0.03] p-3 outline-none"
    >
      <div className="mb-2 flex items-center gap-2">
        {episodeNo != null && <Typography.Text type="secondary">第 {episodeNo} 集</Typography.Text>}
        <Typography.Text strong ellipsis className="flex-1">
          {title ?? `素材 #${mediaId}`}
        </Typography.Text>
        {onClose && (
          <Button size="small" type="text" icon={<CloseOutlined />} onClick={onClose} />
        )}
      </div>

      <div className="relative flex justify-center rounded bg-black/60" style={{ minHeight: mediaKind === 'audio' ? 96 : 200 }}>
        {!token ? (
          <Spin className="self-center" />
        ) : (
          <video
            ref={videoRef}
            className={mediaKind === 'audio' ? 'h-24 w-full' : 'max-h-[62vh] w-full'}
            controlsList="nodownload noremoteplayback"
            disablePictureInPicture
            onContextMenu={(e) => e.preventDefault()}
            onLoadedMetadata={handleLoadedMetadata}
            onTimeUpdate={handleTimeUpdate}
            onPlay={() => setPlaying(true)}
            onPause={() => {
              setPlaying(false)
              savePosition()
            }}
            onEnded={() => setPlaying(false)}
            onError={() => void message.error('播放失败：凭证可能已过期，正在自动刷新重试')}
          />
        )}
        {/* 防盗角标：用户名+日期（安全不依赖此层，服务端水印为主） */}
        <div className="pointer-events-none absolute right-2 top-2 rounded bg-black/50 px-2 py-0.5 text-xs text-white/70">
          {username ?? '已授权用户'} · {todayLabel}
        </div>
        {/* 当前字幕句叠加 */}
        {activeCueIndex >= 0 && mediaKind === 'video' && (
          <div className="pointer-events-none absolute bottom-2 left-1/2 max-w-[90%] -translate-x-1/2 rounded bg-black/60 px-3 py-1 text-center text-sm text-white/90">
            {cues[activeCueIndex].text}
          </div>
        )}
      </div>

      {/* 自定义进度条：命中区间高亮 + 点击/拖拽 seek */}
      <div
        role="slider"
        aria-label="播放进度"
        aria-valuemin={0}
        aria-valuemax={Math.round(durationMs)}
        aria-valuenow={Math.round(currentMs)}
        tabIndex={-1}
        className="relative mt-3 h-2.5 cursor-pointer rounded bg-white/10"
        onClick={(event) => {
          const bar = event.currentTarget
          const ratio = (event.clientX - bar.getBoundingClientRect().left) / bar.getBoundingClientRect().width
          seekTo(ratio * (durationMs / 1000))
        }}
      >
        {durationMs > 0 &&
          hitIntervals
            .filter((interval) => interval.endMs > 0 && interval.startMs < durationMs)
            .map((interval, i) => (
              <Tooltip key={i} title={interval.label ?? `命中 ${fmtClock(interval.startMs)}`}>
                <div
                  className="absolute inset-y-0 rounded bg-amber-400/70"
                  style={{
                    left: `${(Math.max(0, interval.startMs) / durationMs) * 100}%`,
                    width: `${(Math.min(interval.endMs, durationMs) - Math.max(0, interval.startMs)) / durationMs * 100}%`,
                  }}
                />
              </Tooltip>
            ))}
        <div
          className="pointer-events-none absolute inset-y-0 left-0 rounded bg-sky-500"
          style={{ width: `${progressRatio * 100}%` }}
        />
        <div
          className="pointer-events-none absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-sky-300"
          style={{ left: `${progressRatio * 100}%` }}
        />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button
          type="text"
          icon={<StepBackwardOutlined />}
          disabled={prevMediaId == null}
          onClick={() => prevMediaId != null && onEpisodeChange?.(prevMediaId)}
        >
          上一集
        </Button>
        <Button
          type="primary"
          ghost
          icon={playing ? <PauseOutlined /> : <PlayCircleOutlined />}
          onClick={togglePlay}
        >
          {playing ? '暂停' : '播放'}
        </Button>
        <Button
          type="text"
          icon={<StepForwardOutlined />}
          disabled={nextMediaId == null}
          onClick={() => nextMediaId != null && onEpisodeChange?.(nextMediaId)}
        >
          下一集
        </Button>
        <Typography.Text className="text-xs tabular-nums">
          {fmtClock(currentMs)} / {fmtClock(durationMs)}
        </Typography.Text>
        <div className="ml-auto flex items-center gap-3">
          <Select
            size="small"
            value={rate}
            options={RATE_OPTIONS.map((r) => ({ value: r, label: `${r}×` }))}
            onChange={(value) => {
              setRate(value)
              localStorage.setItem(RATE_STORAGE_KEY, String(value))
            }}
            className="w-20"
          />
          <Slider
            className="w-24"
            min={0}
            max={1}
            step={0.1}
            value={volume}
            tooltip={{ open: false }}
            onChange={(value) => setVolume(value as number)}
          />
          <Button
            size="small"
            type="text"
            icon={<FullscreenOutlined />}
            onClick={() => void videoRef.current?.requestFullscreen?.()}
          />
        </div>
      </div>

      {/* 字幕联动：文稿即导航（当前句高亮 + 点句 seek） */}
      {cues.length > 0 && (
        <div className="mt-3 max-h-56 overflow-y-auto rounded border border-white/10 bg-white/[0.02] p-2">
          {cues.map((cue, index) => (
            <div
              key={index}
              ref={index === activeCueIndex ? activeCueRef : undefined}
              className={`cursor-pointer rounded px-2 py-1 text-xs leading-5 ${
                index === activeCueIndex
                  ? 'bg-sky-500/20 text-sky-200'
                  : 'text-[#8a8f98] hover:bg-white/5'
              }`}
              onClick={() => seekTo(cue.startMs / 1000)}
            >
              <span className="mr-2 tabular-nums">{fmtClock(cue.startMs)}</span>
              {cue.text}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
