import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { BoardSkeleton } from './BoardSkeleton'

describe('BoardSkeleton', () => {
  it('主板骨架：按版图坐标渲染占位灰块并暴露加载语义', () => {
    const { container } = render(<BoardSkeleton />)
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', '主板加载中')
    expect(container.querySelectorAll('.animate-pulse').length).toBeGreaterThanOrEqual(10)
  })
})
