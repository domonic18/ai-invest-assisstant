import type { ReactNode } from 'react'

interface SourceNoteProps {
  children: ReactNode
}

export function SourceNote({ children }: SourceNoteProps) {
  return (
    <div className="mt-3 text-center text-xs text-gray-500">
      数据来源: {children}
    </div>
  )
}
