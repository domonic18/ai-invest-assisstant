import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/hooks/useAdminKb', () => ({
  useKbTranscript: vi.fn(),
  useSaveKbTranscript: vi.fn(),
}))

import { useKbTranscript, useSaveKbTranscript } from '@/hooks/useAdminKb'
import type { ApiKbMediaResponse, ApiKbTranscriptResponse } from '@ai-invest/shared'

import { TranscriptEditor } from './TranscriptEditor'

const mockedTranscript = vi.mocked(useKbTranscript)
const mockedSave = vi.mocked(useSaveKbTranscript)

const media = {
  id: 5,
  sourceId: 1,
  mediaKind: 'video',
  episodeNo: 1,
  title: '第 1 集',
  fileName: 'e1.mp4',
} as ApiKbMediaResponse

const transcript: ApiKbTranscriptResponse = {
  mediaId: 5,
  editedAt: null,
  segments: [
    { seqNo: 1, text: '句壹', startMs: 0, endMs: 10000, pageStart: null, pageEnd: null },
    { seqNo: 2, text: '句贰', startMs: 10000, endMs: 20000, pageStart: null, pageEnd: null },
  ],
}

function setup(transcriptData: ApiKbTranscriptResponse | undefined, loading = false) {
  mockedTranscript.mockReturnValue({
    data: transcriptData,
    isLoading: loading,
  } as never)
  const mutateAsync = vi.fn().mockResolvedValue({
    mediaId: 5,
    editedAt: '2026-09-19T03:00:00Z',
    updatedCount: 1,
  })
  mockedSave.mockReturnValue({ mutateAsync, isPending: false } as never)
  return { mutateAsync }
}

describe('TranscriptEditor', () => {
  it('renders segments with seq and timecode', () => {
    setup(transcript)
    render(<TranscriptEditor sourceId={1} media={media} open onClose={vi.fn()} />)
    expect(screen.getByDisplayValue('句壹')).toBeInTheDocument()
    expect(screen.getByDisplayValue('句贰')).toBeInTheDocument()
    expect(screen.getByText('#1')).toBeInTheDocument()
    expect(screen.getByText('00:00')).toBeInTheDocument()
    expect(screen.getByText('00:10')).toBeInTheDocument()
  })

  it('shows empty state for media without transcript', () => {
    setup(undefined)
    render(<TranscriptEditor sourceId={1} media={media} open onClose={vi.fn()} />)
    expect(screen.getByText(/暂无文稿/)).toBeInTheDocument()
  })

  it('saves full draft and reports updated count after edit', async () => {
    const { mutateAsync } = setup(transcript)
    render(<TranscriptEditor sourceId={1} media={media} open onClose={vi.fn()} />)

    const first = screen.getByDisplayValue('句壹')
    fireEvent.change(first, { target: { value: '句壹（校正）' } })

    await waitFor(() => {
      expect(screen.getByText('1 处待保存')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('保存'))

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({
        mediaId: 5,
        data: {
          segments: [
            { seqNo: 1, text: '句壹（校正）' },
            { seqNo: 2, text: '句贰' },
          ],
        },
      })
    })
    expect(await screen.findByText('已保存 1 处修改，待重新索引')).toBeInTheDocument()
  })

  it('keeps save disabled visual when no change', () => {
    setup(transcript)
    render(<TranscriptEditor sourceId={1} media={media} open onClose={vi.fn()} />)
    const save = screen.getByText('保存').closest('a') as HTMLAnchorElement
    expect(save.className).toContain('opacity-50')
  })
})
