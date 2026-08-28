import type React from 'react'

export function IndicatorButton({
  active,
  label,
  icon,
  onClick,
}: {
  active: boolean
  label: string
  icon: React.ReactNode
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-1 px-2 py-0.5 text-xs rounded transition-colors ${
        active
          ? 'bg-[#2a2e38] text-[#d1d4dc]'
          : 'text-[#8c8c8c] hover:text-[#d1d4dc] hover:bg-[#1a1d24]'
      }`}
    >
      {icon}
      {label}
    </button>
  )
}
