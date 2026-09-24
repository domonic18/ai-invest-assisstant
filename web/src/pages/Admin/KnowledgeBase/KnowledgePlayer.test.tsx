import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/kb', () => ({
  fetchKbPlaybackToken: vi.fn(),
  fetchKbSubtitles: vi.fn(),
  kbStreamUrl: vi.fn(
    (mediaId: number, token: string) => `/api/v1/kb/stream/${mediaId}?token=${token}`
  ),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: (selector: (s: { user: { username: string } }) => unknown) =>
    selector({ user: { username: 'alice' } }),
}))

import { fetchKbPlaybackToken, fetchKbSubtitles } from '@/api/kb'

import { KnowledgePlayer } from './KnowledgePlayer'
import { parseVttCues } from './playerUtils'

const mockedToken = vi.mocked(fetchKbPlaybackToken)
const mockedSubtitles = vi.mocked(fetchKbSubtitles)

const STREAM_SRC = '/api/v1/kb/stream/3?token=tok-abc'

const VTT = [
  'WEBVTT',
  '',
  '00:00:01.000 --> 00:00:03.500',
  '支撑线的画法',
  '',
  '00:00:10.000 --> 00:00:12.000',
  '回踩不破可买入',
  '',
].join('\n')

async function renderPlayer(
  props?: Partial<Parameters<typeof KnowledgePlayer>[0]>
) {
  const utils = render(
    <KnowledgePlayer mediaId={3} mediaKind="video" title="均线入门课" episodeNo={3} {...props} />
  )
  const video = (await waitFor(() => {
    const el = utils.container.querySelector('video')
    expect(el).not.toBeNull()
    return el as HTMLMediaElement
  })) as HTMLMediaElement
  // jsdom 媒体不实现播放，duration 恒 NaN；显式给定以驱动 seek/进度逻辑
  Object.defineProperty(video, 'duration', { value: 120, configurable: true })
  return { ...utils, video }
}

describe('KnowledgePlayer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    window.HTMLElement.prototype.scrollIntoView = vi.fn()
    vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined)
    vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {})
    vi.spyOn(HTMLMediaElement.prototype, 'load').mockImplementation(() => {})
    mockedToken.mockResolvedValue({
      token: 'tok-abc',
      expiresIn: 1800,
      mediaId: 3,
      prevMediaId: 2,
      nextMediaId: 4,
      pageCount: null,
    })
    mockedSubtitles.mockResolvedValue(VTT)
  })

  it('loads playback token and wires stream src with anti-download attributes', async () => {
    const { video } = await renderPlayer()

    expect(mockedToken).toHaveBeenCalledWith(3)
    expect(video.getAttribute('src')).toBe(STREAM_SRC)
    expect(video.getAttribute('controlsList')).toContain('nodownload')
    expect(video.hasAttribute('disablepictureinpicture')).toBe(true)
    // 防盗角标：用户名 + 日期
    expect(screen.getByText(/alice · \d{4}-\d{2}-\d{2}/)).toBeInTheDocument()
  })

  it('renders transcript from vtt and clicking a line seeks to cue start', async () => {
    const { video } = await renderPlayer()

    expect(await screen.findByText('支撑线的画法')).toBeInTheDocument()
    fireEvent.click(screen.getByText('回踩不破可买入'))
    expect(video.currentTime).toBe(10)
  })

  it('highlights active cue and overlays current subtitle line on timeupdate', async () => {
    const { video } = await renderPlayer()
    await screen.findByText('支撑线的画法')

    video.dispatchEvent(new Event('loadedmetadata'))
    video.currentTime = 11
    video.dispatchEvent(new Event('timeupdate'))
    await waitFor(() => {
      // 转写列表 + 视频叠加各渲染一次当前句
      expect(screen.getAllByText('回踩不破可买入')).toHaveLength(2)
    })
    // [0] 是视频底部叠加句，[1] 是转写列表当前句
    const active = screen.getAllByText('回踩不破可买入')[1]
    expect(active.className).toContain('bg-sky-500/20')
    expect(window.HTMLElement.prototype.scrollIntoView).toHaveBeenCalled()
    expect(screen.getByText('00:11 / 02:00')).toBeInTheDocument()
  })

  it('navigates episodes via prev/next buttons from token response', async () => {
    const onEpisodeChange = vi.fn()
    await renderPlayer({ onEpisodeChange })

    fireEvent.click(screen.getByRole('button', { name: /上一集/ }))
    expect(onEpisodeChange).toHaveBeenCalledWith(2)
    fireEvent.click(screen.getByRole('button', { name: /下一集/ }))
    expect(onEpisodeChange).toHaveBeenCalledWith(4)
  })

  it('applies initialSeekMs after metadata load and marks hit intervals on progress bar', async () => {
    const { video } = await renderPlayer({
      initialSeekMs: 25_000,
      hitIntervals: [{ startMs: 10_000, endMs: 40_000 }],
    })

    video.dispatchEvent(new Event('loadedmetadata'))
    await waitFor(() => expect(video.currentTime).toBe(25))
    expect(screen.getByText('00:25 / 02:00')).toBeInTheDocument()
    expect(document.querySelector('.bg-amber-400\\/70')).not.toBeNull()
  })

  it('resumes from saved localStorage position when no explicit seek provided', async () => {
    localStorage.setItem('kb-player-pos:3', '42')
    const { video } = await renderPlayer()

    video.dispatchEvent(new Event('loadedmetadata'))
    await waitFor(() => expect(video.currentTime).toBe(42))
  })

  it('changing rate persists to localStorage and applies without reloading stream', async () => {
    const { video } = await renderPlayer()
    expect(video.playbackRate).toBe(1)

    fireEvent.mouseDown(screen.getByRole('combobox'))
    fireEvent.click(screen.getByTitle('2×'))
    await waitFor(() => expect(video.playbackRate).toBe(2))
    expect(localStorage.getItem('kb-player-rate')).toBe('2')
    // 倍速切换不得重载视频（防进度归零）
    expect(video.getAttribute('src')).toBe(STREAM_SRC)
  })

  it('play button and ArrowRight keyboard seek operate the media element', async () => {
    const { container, video } = await renderPlayer()
    video.currentTime = 10

    fireEvent.click(screen.getByRole('button', { name: /播放/ }))
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalled()

    fireEvent.keyDown(container.firstChild as HTMLElement, { key: 'ArrowRight' })
    expect(video.currentTime).toBe(15)
  })

  it('parseVttCues tolerates comma millisecond separators', () => {
    const cues = parseVttCues('WEBVTT\n\n00:00:01,500 --> 00:00:03,000\n你好')
    expect(cues).toEqual([{ startMs: 1500, endMs: 3000, text: '你好' }])
  })
})
