import { FileOutlined, FileTextOutlined, FolderOutlined } from '@ant-design/icons'
import { Segmented, Skeleton, Typography } from 'antd'
import { useEffect, useState } from 'react'

import type { ApiSkillFile } from '@ai-invest/shared'

import { MarkdownText } from '@/components/common/MarkdownText'
import { useSkillFiles } from '@/hooks/useSkills'

function formatSize(size: number): string {
  return size >= 1024 ? `${(size / 1024).toFixed(1)} KB` : `${size} B`
}

function isMarkdown(path: string): boolean {
  return path.toLowerCase().endsWith('.md')
}

interface SkillFileBrowserViewProps {
  /** 目录树与面包屑展示的根目录名（技能 id）。 */
  rootLabel: string
  files: ApiSkillFile[] | undefined
  isLoading: boolean
  isError?: boolean
  /** 虚拟合成文件提示（技能广场合成口径，镜像直读不传）。 */
  synthetic?: boolean
}

/** 技能包文件浏览器展示层：左侧文件列表 + 右侧 预览/源码 内容区。
 * 数据获取由调用方包装（技能广场走 useSkillFiles；Agent 配置页走镜像直读 API）。 */
export function SkillFileBrowserView({
  rootLabel,
  files,
  isLoading,
  isError = false,
  synthetic = false,
}: SkillFileBrowserViewProps) {
  const [activePath, setActivePath] = useState<string | null>(null)
  const [view, setView] = useState<'preview' | 'source'>('preview')

  useEffect(() => {
    if (files == null || !files.length) return
    if (!files.some((file) => file.path === activePath)) {
      setActivePath(files[0].path)
      setView('preview')
    }
  }, [files, activePath])

  const activeFile = files?.find((file) => file.path === activePath) ?? null
  const markdown = activeFile != null && isMarkdown(activeFile.path)

  return (
    <div className="flex min-h-0 flex-1">
      <aside className="w-60 shrink-0 overflow-y-auto border-r border-[#23262d] px-2.5 py-3 max-w-[45%]">
        <div className="px-2 pb-2 text-[11px] font-semibold tracking-wider text-[#5c616e]">
          技能包结构
        </div>
        <div className="flex items-center gap-1.5 px-2 py-1 font-mono text-xs font-semibold text-[#f0f1f5]">
          <FolderOutlined className="text-[#5c616e]" />
          <span className="truncate">{rootLabel}</span>
        </div>
        {isLoading ? (
          <div className="px-2 pt-2">
            <Skeleton active title={false} paragraph={{ rows: 2 }} />
          </div>
        ) : (
          files?.map((file) => {
            const active = file.path === activePath
            return (
              <button
                key={file.path}
                type="button"
                onClick={() => setActivePath(file.path)}
                className={`flex w-full items-center gap-2 rounded px-2 py-1.5 pl-5 text-left transition-colors ${
                  active
                    ? 'bg-[rgba(94,106,210,0.10)] text-[#5e6ad2]'
                    : 'text-[#8a8f98] hover:bg-[#1c1f26] hover:text-[#f0f1f5]'
                }`}
              >
                {isMarkdown(file.path) ? (
                  <FileTextOutlined className="text-[11px]" />
                ) : (
                  <FileOutlined className="text-[11px]" />
                )}
                <span className="flex-1 min-w-0 truncate font-mono text-xs">
                  {file.path}
                </span>
                <span className="shrink-0 text-[10px] text-[#5c616e]">
                  {formatSize(file.size)}
                </span>
              </button>
            )
          })
        )}
        {synthetic && (
          <div className="mt-3 border-t border-[#23262d] px-2 pt-2 text-[10.5px] leading-relaxed text-[#5c616e]">
            文件由技能配置合成（虚拟文件），非镜像内真实路径。
          </div>
        )}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex shrink-0 flex-wrap items-center gap-1.5 border-b border-[#23262d] px-4 py-2 font-mono text-[11.5px] text-[#5c616e]">
          <span>skills</span>
          <span>/</span>
          <span className="truncate">{rootLabel}</span>
          {activeFile && (
            <>
              <span>/</span>
              <span className="truncate font-medium text-[#f0f1f5]">
                {activeFile.path}
              </span>
            </>
          )}
        </div>
        {activeFile && markdown && (
          <div className="shrink-0 px-4 pt-2.5">
            <Segmented
              size="small"
              value={view}
              onChange={(value) => setView(value as 'preview' | 'source')}
              options={[
                { label: '预览', value: 'preview' },
                { label: '源码', value: 'source' },
              ]}
            />
          </div>
        )}
        <div className="flex-1 overflow-y-auto px-4 pb-4 pt-2">
          {!activeFile ? (
            isError ? (
              <Typography.Text type="secondary" className="text-xs">
                技能包文件加载失败
              </Typography.Text>
            ) : (
              <Typography.Text type="secondary" className="text-xs">
                暂无文件
              </Typography.Text>
            )
          ) : markdown && view === 'preview' ? (
            <MarkdownText
              content={activeFile.content}
              className="text-xs [&_h1]:mb-3 [&_h1]:border-b [&_h1]:border-[#23262d] [&_h1]:pb-2 [&_h1]:text-lg [&_h1]:font-semibold [&_h1]:text-[#f0f1f5] [&_h2]:mb-2 [&_h2]:mt-4 [&_h2]:text-sm [&_h2]:font-semibold [&_h2]:text-[#f0f1f5] [&_h3]:mb-1.5 [&_h3]:mt-3 [&_h3]:text-[13px] [&_h3]:font-semibold [&_h3]:text-[#f0f1f5] [&_li]:text-xs [&_li]:text-[#8a8f98] [&_p]:text-xs [&_p]:text-[#8a8f98] [&_pre]:text-[11px]"
            />
          ) : (
            <pre className="overflow-auto rounded-md border border-[#23262d] bg-[#0a0c10] p-3 text-xs leading-relaxed whitespace-pre-wrap text-[#9ecbff]">
              {activeFile.content}
            </pre>
          )}
        </div>
      </div>
    </div>
  )
}

interface SkillFileBrowserProps {
  skillId: string
}

/** 技能广场文件浏览器（数据包装：useSkillFiles → 展示层）。 */
export function SkillFileBrowser({ skillId }: SkillFileBrowserProps) {
  const filesQ = useSkillFiles(skillId)
  return (
    <SkillFileBrowserView
      rootLabel={skillId}
      files={filesQ.data?.files}
      isLoading={filesQ.isLoading}
      isError={filesQ.isError}
      synthetic={filesQ.data?.synthetic}
    />
  )
}
