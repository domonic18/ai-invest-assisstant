import { Skeleton } from 'antd'

export function PageSkeleton() {
  return (
    <div className="p-6 space-y-4">
      <Skeleton active paragraph={{ rows: 8 }} />
    </div>
  )
}
