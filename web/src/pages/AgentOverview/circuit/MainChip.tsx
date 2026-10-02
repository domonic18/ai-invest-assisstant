/**
 * 中央主控：复盘引擎 RV-ENGINE-01（平台固定件，非 Agent）+ 25MHz 晶振。
 * CORE die 呼吸 + 计划→盯盘→归因流水子核 LED 跑马，REV4 起子核复用 led 编排。
 */
import { BOARD } from './boardTheme'

const TOP_PINS = [446, 470, 494, 518, 542, 566, 590, 614]
const BOTTOM_PINS = [446, 470, 494, 518, 542, 566, 590, 614]

export function MainChip() {
  return (
    <>
      <g>
        <g fill={BOARD.pin}>
          {TOP_PINS.map((x) => (
            <rect key={`t${x}`} x={x} y="330" width="10" height="4" />
          ))}
          {BOTTOM_PINS.map((x) => (
            <rect key={`b${x}`} x={x} y="484" width="10" height="4" />
          ))}
        </g>
        <rect x="430" y="334" width="210" height="150" rx="10" fill="#10181440" stroke="rgba(52,211,153,.55)" strokeWidth="1.6" />
        <rect x="436" y="340" width="198" height="138" rx="7" fill="none" stroke="rgba(255,255,255,.05)" strokeWidth="1" />
        <text x="535" y="352" textAnchor="middle" fontSize="8" fill={BOARD.textFaint} letterSpacing="1">
          RV-ENGINE-01
        </text>
        <rect x="505" y="358" width="60" height="60" rx="6" fill="url(#ahc-dieGreen)" className="ahc-corebeat" />
        <rect x="505" y="358" width="60" height="60" rx="6" fill="none" stroke={BOARD.green} strokeWidth="1.2" />
        <text x="535" y="392" textAnchor="middle" fontSize="9" fill="#07120d" fontWeight="700">
          CORE
        </text>
        <g>
          {(['计划', '盯盘', '归因'] as const).map((label, i) => {
            const x = 452 + i * 48
            return (
              <g key={label}>
                <rect x={x} y="430" width="36" height="22" rx="4" fill="rgba(52,211,153,.12)" stroke="rgba(52,211,153,.4)" />
                <rect x={x} y="430" width="36" height="22" rx="4" fill="url(#ahc-dieGreen)" className={`ahc-led${i + 1}`} />
                <text x={x + 18} y="445" textAnchor="middle" fontSize="8.5" fill={BOARD.greenPale}>
                  {label}
                </text>
                {i < 2 && <path d={`M${x + 38} 441 H${x + 46}`} stroke="rgba(52,211,153,.5)" strokeWidth="1.2" />}
              </g>
            )
          })}
          <path d="M588 441 H606 V400 H571" fill="none" stroke="rgba(52,211,153,.3)" strokeWidth="1" strokeDasharray="2 3" />
        </g>
        <text x="535" y="502" textAnchor="middle" fontSize="11" fill={BOARD.greenSoft} letterSpacing="1">
          复盘引擎 · 主控
        </text>
      </g>

      {/* 晶振（时钟源） */}
      <g>
        <rect x="594" y="529" width="32" height="32" rx="6" fill="#0e1512" stroke="rgba(148,163,184,.5)" strokeWidth="1.2" />
        <path d="M602 535 V555 M618 535 V555" stroke="rgba(148,163,184,.6)" strokeWidth="1.4" />
        <rect x="605" y="539" width="10" height="12" rx="2" fill="none" stroke="rgba(148,163,184,.4)" />
        <text x="610" y="575" textAnchor="middle" fontSize="8.5" fill={BOARD.grey}>
          25MHz
        </text>
      </g>
    </>
  )
}
