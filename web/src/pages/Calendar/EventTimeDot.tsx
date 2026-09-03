/** 日级事件的时刻位占位：SVG 圆点，颜色随类别（currentColor）。 */
export function EventTimeDot({ className = '' }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 8 8"
      width="8"
      height="8"
      aria-hidden="true"
      className={`inline-block align-[-1px] ${className}`}
    >
      <circle cx="4" cy="4" r="4" fill="currentColor" />
    </svg>
  )
}
