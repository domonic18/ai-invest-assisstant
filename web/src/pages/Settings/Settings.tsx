/**
 * 个人设置页：侧边锚点导航（IntersectionObserver 高亮）+ 各 section 组件拼装。
 * section 内容见 components/（Profile/Appearance/Indexes/Quota/Model/Security）。
 */

import { Typography } from 'antd'
import { useEffect, useState } from 'react'

import { AppearanceSection } from './components/AppearanceSection'
import { IndexesSection } from './components/IndexesSection'
import { MyModelSection } from './components/MyModelSection'
import { ProfileSection } from './components/ProfileSection'
import { QuotaSection } from './components/QuotaSection'
import { SecuritySection } from './components/SecuritySection'

const SECTIONS = [
  { key: 'profile', label: '基本信息' },
  { key: 'appearance', label: '外观偏好' },
  { key: 'indexes', label: '跟踪指数' },
  { key: 'quota', label: '配额与用量' },
  { key: 'model', label: '我的模型' },
  { key: 'security', label: '账号安全' },
] as const

type SectionKey = (typeof SECTIONS)[number]['key']

export function Settings() {
  const [activeSection, setActiveSection] = useState<SectionKey>('profile')

  useEffect(() => {
    const sections = SECTIONS.map((s) => document.getElementById(`sec-${s.key}`)).filter(
      (el): el is HTMLElement => el != null,
    )
    if (!sections.length) return
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id.replace('sec-', '') as SectionKey)
          }
        }
      },
      { rootMargin: '-10% 0px -75% 0px' },
    )
    sections.forEach((section) => observer.observe(section))
    return () => observer.disconnect()
  }, [])

  return (
    <div className="max-w-4xl">
      <Typography.Title level={4} className="!mb-0">个人设置</Typography.Title>
      <Typography.Paragraph type="secondary" className="!mt-1 !mb-4 text-xs">
        账号信息、外观偏好与账号安全集中配置
      </Typography.Paragraph>

      <nav className="md:hidden flex gap-2 overflow-x-auto pb-2 mb-2">
        {SECTIONS.map((section) => (
          <a
            key={section.key}
            href={`#sec-${section.key}`}
            className={`shrink-0 px-3 py-1.5 rounded-full text-xs border transition-colors ${
              activeSection === section.key
                ? 'border-[#5e6ad2] text-[#5e6ad2] bg-[rgba(94,106,210,0.10)]'
                : 'border-[#23262d] text-[#8a8f98]'
            }`}
          >
            {section.label}
          </a>
        ))}
      </nav>

      <div className="flex items-start gap-6">
        <nav className="hidden md:flex flex-col gap-0.5 w-36 shrink-0 sticky top-0">
          <div className="text-[11px] tracking-wider text-[#5c616e] px-3 mb-1.5">设置</div>
          {SECTIONS.map((section) => (
            <a
              key={section.key}
              href={`#sec-${section.key}`}
              className={`block px-3 py-1.5 rounded text-sm border-l-2 transition-colors ${
                activeSection === section.key
                  ? 'text-[#5e6ad2] bg-[rgba(94,106,210,0.10)] border-[#5e6ad2] font-medium'
                  : 'text-[#8a8f98] border-transparent hover:text-[#f0f1f5] hover:bg-[#14161c]'
              }`}
            >
              {section.label}
            </a>
          ))}
        </nav>

        <div className="flex-1 min-w-0 space-y-5">
          <section id="sec-profile" className="scroll-mt-4">
            <ProfileSection />
          </section>

          <section id="sec-appearance" className="scroll-mt-4 space-y-5">
            <AppearanceSection />
          </section>

          <section id="sec-indexes" className="scroll-mt-4">
            <IndexesSection />
          </section>

          <section id="sec-quota" className="scroll-mt-4">
            <QuotaSection />
          </section>

          <section id="sec-model" className="scroll-mt-4">
            <MyModelSection />
          </section>

          <section id="sec-security" className="scroll-mt-4 space-y-5">
            <SecuritySection />
          </section>
        </div>
      </div>
    </div>
  )
}
