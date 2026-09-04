import { APP_VERSION, SITE_NAME_EN, SITE_NAME_ZH } from '@/config/brand'

interface BrandProps {
  size?: 'sm' | 'md' | 'lg'
  centered?: boolean
  showVersion?: boolean
}

const SIZE_MAP = {
  sm: { logo: 'h-6 w-6', en: 'text-base', zh: 'text-[10px]' },
  md: { logo: 'h-8 w-8', en: 'text-lg', zh: 'text-xs' },
  lg: { logo: 'h-12 w-12', en: 'text-2xl', zh: 'text-sm' },
} as const

export function Brand({ size = 'md', centered = false, showVersion = false }: BrandProps) {
  const styles = SIZE_MAP[size]
  return (
    <div className={`flex items-center gap-2.5 ${centered ? 'justify-center' : ''}`}>
      <img src="/logo.svg" alt={SITE_NAME_EN} className={styles.logo} />
      <div className={`flex items-center gap-2 ${centered ? 'text-center' : ''}`}>
        <div>
          <div className={`${styles.en} font-bold text-white leading-tight`}>{SITE_NAME_EN}</div>
          <div className={`${styles.zh} text-gray-400 leading-tight`}>{SITE_NAME_ZH}</div>
        </div>
        {showVersion && (
          <span className="inline-flex items-center rounded border border-blue-800 bg-blue-950/40 px-1.5 py-0.5 text-[10px] font-medium text-blue-300">
            v{APP_VERSION}
          </span>
        )}
      </div>
    </div>
  )
}
