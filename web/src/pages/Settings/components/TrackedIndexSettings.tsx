import { useQuery } from '@tanstack/react-query'
import { App, Button, Checkbox, Spin } from 'antd'
import { useEffect, useState } from 'react'

import { fetchTrackedIndexOptions } from '@/api/trackedIndex'
import { queryKeys } from '@/hooks/queryKeys'
import { useSettingsStore } from '@/stores/settings'

/**
 * 跟踪指数显示配置（用户级，存 users.settings.trackedIndexCodes）。
 * 勾选全部 = 恢复默认（存 null，后续新增指数自动显示）；清空 = 全部不显示。
 */
export function TrackedIndexSettings() {
  const { message } = App.useApp()
  const trackedIndexCodes = useSettingsStore((s) => s.userSettings.trackedIndexCodes)
  const updateTrackedIndexes = useSettingsStore((s) => s.updateTrackedIndexes)

  const optionsQ = useQuery({
    queryKey: queryKeys.trackedIndexOptions,
    queryFn: fetchTrackedIndexOptions,
  })
  const options = optionsQ.data ?? []
  const allCodes = options.map((o) => o.indexCode)

  const [draft, setDraft] = useState<string[] | null>(null)
  const [saving, setSaving] = useState(false)

  // 服务端配置（null=全部）折成具体勾选集；本地有草稿时不覆盖
  useEffect(() => {
    if (!options.length) return
    setDraft((prev) => prev ?? (trackedIndexCodes ?? allCodes))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options.length, trackedIndexCodes])

  const checked = draft ?? []
  const isAll = options.length > 0 && checked.length === options.length

  const handleSave = async () => {
    setSaving(true)
    try {
      // 全选等价于默认（存 null），避免母表新增指数后被旧清单挡住
      await updateTrackedIndexes(isAll ? null : checked)
      message.success('跟踪指数配置已保存')
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  if (optionsQ.isLoading) {
    return <Spin size="small" />
  }

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <Button size="small" onClick={() => setDraft(allCodes)}>
          全选
        </Button>
        <Button size="small" onClick={() => setDraft([])}>
          清空
        </Button>
        <span className="text-xs text-[#5c616e]">
          已选 {checked.length} / {options.length}
        </span>
        <Button
          type="primary"
          size="small"
          className="ml-auto"
          loading={saving}
          onClick={handleSave}
        >
          保存
        </Button>
      </div>
      <Checkbox.Group
        className="grid grid-cols-2 gap-y-2 md:grid-cols-3"
        value={checked}
        onChange={(values) => setDraft(values as string[])}
        options={options.map((o) => ({
          label: `${o.indexName}（${o.indexCode}）`,
          value: o.indexCode,
        }))}
      />
    </div>
  )
}
