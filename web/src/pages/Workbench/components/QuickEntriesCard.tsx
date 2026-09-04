import { Button } from 'antd'
import { Link } from 'react-router-dom'

import { FoldCard } from './FoldCard'

const ENTRIES = [
  { to: '/chain', label: '产业链全景分析' },
  { to: '/research', label: '研报中心' },
  { to: '/hotspot', label: '热点追踪' },
]

interface QuickEntriesCardProps {
  className?: string
}

export function QuickEntriesCard({ className }: QuickEntriesCardProps) {
  return (
    <FoldCard title="快捷入口" className={className}>
      <div className="flex flex-wrap gap-2">
        {ENTRIES.map((entry) => (
          <Link key={entry.to} to={entry.to}>
            <Button>{entry.label}</Button>
          </Link>
        ))}
      </div>
    </FoldCard>
  )
}
