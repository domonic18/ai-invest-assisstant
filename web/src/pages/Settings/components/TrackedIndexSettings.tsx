import { DeleteOutlined, PlusOutlined, SearchOutlined } from '@ant-design/icons'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { App, Button, Checkbox, Empty, Input, Popconfirm, Spin } from 'antd'
import { useEffect, useMemo, useState } from 'react'
import type { ApiTrackedIndexOption } from '@ai-invest/shared'

import { runCollectorTask } from '@/api/collectorAdmin'
import {
  createTrackedIndex,
  deleteTrackedIndex,
  fetchTrackedIndexOptions,
} from '@/api/trackedIndex'
import { queryKeys } from '@/hooks/queryKeys'
import { useSettingsStore } from '@/stores/settings'
import { apiErrorMessage } from '@/utils/errorMessage'
import { changeHex, formatPercent } from '@/utils/formatters'

const A_SHARE_CODE_RE = /^(sh|sz)\d{6}$/
/** 沪市 5xxxxx / 深市 15/16xxxx → ETF 日 K 采集通道，其余 A 股代码走指数通道。 */
const ETF_CODE_RE = /^(sh5\d{5}|sz1[56]\d{4})$/

const GROUP_TITLES: Record<string, string> = {
  A股: 'A股指数 / ETF',
  全球: '全球指标',
}

function OptionRow({
  option,
  checked,
  onToggle,
  onDelete,
}: {
  option: ApiTrackedIndexOption
  checked: boolean
  onToggle: (code: string, next: boolean) => void
  onDelete: (option: ApiTrackedIndexOption) => void
}) {
  return (
    <div className="group flex items-center gap-2 rounded-lg border border-[#23262d] bg-[#181a21] px-3 py-2 transition-colors hover:border-[#3a3f4b]">
      <Checkbox
        checked={checked}
        onChange={(e) => onToggle(option.indexCode, e.target.checked)}
      />
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13px] text-[#f0f1f5]" title={option.indexName}>
          {option.indexName}
        </div>
        <div className="font-mono text-[11px] text-[#5c616e]">{option.indexCode}</div>
      </div>
      <div className="text-right">
        <div className="font-mono text-[13px] font-semibold">
          {option.latestClose != null
            ? option.latestClose.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
            : <span className="text-[#5c616e]">待采集</span>}
        </div>
        <div
          className="font-mono text-[11px] font-semibold"
          style={{ color: changeHex(option.latestChangePct) }}
        >
          {option.latestChangePct != null ? formatPercent(option.latestChangePct) : ''}
        </div>
      </div>
      {option.marketCategory === 'A股' && (
        <Popconfirm
          title="删除该自定义标的？"
          description="仅删除跟踪配置，不影响已采集的历史数据"
          okText="删除"
          cancelText="取消"
          okButtonProps={{ danger: true }}
          onConfirm={() => onDelete(option)}
        >
          <Button
            size="small"
            type="text"
            danger
            icon={<DeleteOutlined />}
            className="!px-1 opacity-0 transition-opacity group-hover:opacity-100"
          />
        </Popconfirm>
      )}
    </div>
  )
}

/**
 * 跟踪指数显示配置（用户级，存 users.settings.trackedIndexCodes）。
 * 勾选全部 = 恢复默认（存 null，后续新增指数自动显示）；清空 = 全部不显示。
 * A 股支持添加任意指数/ETF（自动触发历史 K 线回填）；全球指标暂限内置清单。
 */
export function TrackedIndexSettings() {
  const { message } = App.useApp()
  const queryClient = useQueryClient()
  const trackedIndexCodes = useSettingsStore((s) => s.userSettings.trackedIndexCodes)
  const updateTrackedIndexes = useSettingsStore((s) => s.updateTrackedIndexes)

  const optionsQ = useQuery({
    queryKey: queryKeys.trackedIndexOptions,
    queryFn: fetchTrackedIndexOptions,
  })
  const options = useMemo(() => optionsQ.data ?? [], [optionsQ.data])
  const allCodes = options.map((o) => o.indexCode)

  const [draft, setDraft] = useState<string[] | null>(null)
  const [saving, setSaving] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [newCode, setNewCode] = useState('')
  const [newName, setNewName] = useState('')
  const [adding, setAdding] = useState(false)

  // 服务端配置（null=全部）折成具体勾选集；本地有草稿时不覆盖
  useEffect(() => {
    if (!options.length) return
    setDraft((prev) => prev ?? (trackedIndexCodes ?? allCodes))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options.length, trackedIndexCodes])

  const checked = draft ?? []
  const isAll = options.length > 0 && checked.length === options.length

  const groups = useMemo(() => {
    const kw = keyword.trim().toLowerCase()
    const filtered = kw
      ? options.filter(
          (o) =>
            o.indexName.toLowerCase().includes(kw) ||
            o.indexCode.toLowerCase().includes(kw),
        )
      : options
    const map = new Map<string, ApiTrackedIndexOption[]>()
    for (const option of filtered) {
      map.set(option.marketCategory, [...(map.get(option.marketCategory) ?? []), option])
    }
    return map
  }, [options, keyword])

  const handleSave = async () => {
    setSaving(true)
    try {
      // 全选等价于默认（存 null），避免新增指数后被旧清单挡住
      await updateTrackedIndexes(isAll ? null : checked)
      message.success('跟踪指数配置已保存')
    } catch (err) {
      message.error(apiErrorMessage(err, '保存失败'))
    } finally {
      setSaving(false)
    }
  }

  const handleAdd = async () => {
    const code = newCode.trim().toLowerCase()
    const name = newName.trim()
    if (!A_SHARE_CODE_RE.test(code)) {
      message.warning('代码格式：sh/sz + 6 位数字，如 sh000905、sz159915')
      return
    }
    if (!name) {
      message.warning('请填写显示名称')
      return
    }
    if (options.some((o) => o.indexCode === code)) {
      message.warning('该代码已在跟踪清单中')
      return
    }
    setAdding(true)
    try {
      await createTrackedIndex({
        indexCode: code,
        indexName: name,
        marketCategory: 'A股',
        dataSource: 'sina',
      })
      await queryClient.invalidateQueries({ queryKey: queryKeys.trackedIndexOptions })
      setDraft((prev) => {
        const base = prev ?? (trackedIndexCodes ?? allCodes)
        return [...base, code]
      })
      setNewCode('')
      setNewName('')
      // 立即回填历史 K 线，行情卡无需等下一次定时采集
      const task = ETF_CODE_RE.test(code) ? 'etf-kline' : 'index-kline'
      runCollectorTask(task, { symbols: [code] }).catch(() => {
        message.info(`${name} 已添加；历史数据回填任务触发失败，可稍后在管理后台手动执行 ${task}`)
      })
      message.success(`${name} 已添加，正在回填历史行情`)
    } catch (err) {
      message.error(apiErrorMessage(err, '添加失败'))
    } finally {
      setAdding(false)
    }
  }

  const handleDelete = async (option: ApiTrackedIndexOption) => {
    try {
      await deleteTrackedIndex(option.id)
      await queryClient.invalidateQueries({ queryKey: queryKeys.trackedIndexOptions })
      setDraft((prev) => (prev ?? (trackedIndexCodes ?? allCodes)).filter(
        (code) => code !== option.indexCode,
      ))
      message.success(`${option.indexName} 已删除`)
    } catch (err) {
      message.error(apiErrorMessage(err, '删除失败'))
    }
  }

  if (optionsQ.isLoading) {
    return <Spin size="small" />
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Input
          size="small"
          prefix={<SearchOutlined className="!text-[#5c616e]" />}
          placeholder="搜索名称或代码"
          allowClear
          className="!w-48"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
        />
        <span className="text-xs text-[#5c616e]">
          已选 {checked.length} / {options.length}
        </span>
        <div className="ml-auto flex items-center gap-2">
          <Button size="small" onClick={() => setDraft(allCodes)}>
            全选
          </Button>
          <Button size="small" onClick={() => setDraft([])}>
            清空
          </Button>
          <Button type="primary" size="small" loading={saving} onClick={handleSave}>
            保存
          </Button>
        </div>
      </div>

      <div className="rounded-lg border border-[#23262d] bg-[#14161b] p-2.5">
        <div className="mb-2 flex items-center gap-2 px-0.5">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-[#8a8f98]">
            添加 A 股指数 / ETF
          </span>
          <span className="text-[11px] text-[#5c616e]">示例：sh000905 中证500、sz159915 创业板ETF</span>
        </div>
        <div className="flex items-center gap-2">
          <Input
            size="small"
            placeholder="代码 sh000905"
            className="!w-40"
            value={newCode}
            onChange={(e) => setNewCode(e.target.value)}
            onPressEnter={handleAdd}
          />
          <Input
            size="small"
            placeholder="显示名称"
            className="!w-44"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onPressEnter={handleAdd}
          />
          <Button size="small" icon={<PlusOutlined />} loading={adding} onClick={handleAdd}>
            添加并跟踪
          </Button>
        </div>
      </div>

      {options.length === 0 ? (
        <Empty
          description="暂无可勾选的跟踪指数，可在上方添加 A 股指数 / ETF"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      ) : (
        [...groups.entries()].map(([category, items]) => (
          <div key={category}>
            <div className="mb-1.5 px-0.5 text-[11px] font-semibold text-[#5c616e]">
              {GROUP_TITLES[category] ?? category}
              {category === '全球' && (
                <span className="ml-2 font-normal">（内置清单，暂不支持自定义）</span>
              )}
            </div>
            <div className="grid grid-cols-1 gap-1.5 md:grid-cols-2">
              {items.map((option) => (
                <OptionRow
                  key={option.indexCode}
                  option={option}
                  checked={checked.includes(option.indexCode)}
                  onToggle={(code, next) =>
                    setDraft((prev) => {
                      const base = new Set(prev ?? (trackedIndexCodes ?? allCodes))
                      if (next) base.add(code)
                      else base.delete(code)
                      return [...base]
                    })
                  }
                  onDelete={handleDelete}
                />
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  )
}
