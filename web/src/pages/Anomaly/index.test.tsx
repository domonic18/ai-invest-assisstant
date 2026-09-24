import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

vi.mock('./SectorAnomalyPage', () => ({
  SectorAnomalyPage: () => <div data-testid="sector-stub" />,
}))
vi.mock('./StockAnomalyPage', () => ({
  StockAnomalyPage: () => <div data-testid="stock-stub" />,
}))

import { AnomalyPage } from './index'

function renderPage(route: string) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AnomalyPage />
    </MemoryRouter>
  )
}

describe('AnomalyPage', () => {
  it('defaults to sector tab', () => {
    renderPage('/anomaly/sector')
    expect(screen.getByTestId('sector-stub')).toBeInTheDocument()
    expect(screen.getByRole('tab', { selected: true })).toHaveTextContent('板块异动')
  })

  it('stock route activates stock tab', () => {
    renderPage('/anomaly/stock')
    expect(screen.getByTestId('stock-stub')).toBeInTheDocument()
    expect(screen.getByRole('tab', { selected: true })).toHaveTextContent('个股异动')
  })

  it('tab click navigates between routes', () => {
    renderPage('/anomaly/sector')
    fireEvent.click(screen.getByRole('tab', { name: '个股异动' }))
    expect(screen.getByTestId('stock-stub')).toBeInTheDocument()
  })
})
