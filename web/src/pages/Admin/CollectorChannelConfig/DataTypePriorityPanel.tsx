import { Alert, Collapse, Typography, message } from 'antd'
import { useMemo, useState } from 'react'

import { useCollectorChannelConfigs } from '@/hooks/useCollectorChannelConfigs'
import {
  useCollectorDataTypeChannels,
  useReplaceDataTypeChannels,
} from '@/hooks/useCollectorDataTypeChannels'
import type { CollectorDataTypeChannel } from '@ai-invest/shared'

import { ChannelDebugModal } from './ChannelDebugModal'
import type { ChannelDebugTarget } from './ChannelDebugModal'
import { DATA_TYPE_GROUPS } from './constants'
import { TypePrioritySection } from './TypePrioritySection'

interface DebugState {
  target: ChannelDebugTarget
  presetDataType: string
}

export function DataTypePriorityPanel() {
  const { data: dataTypes, isLoading, error } = useCollectorDataTypeChannels()
  const { data: allChannels } = useCollectorChannelConfigs()
  const replaceMutation = useReplaceDataTypeChannels()

  const [drafts, setDrafts] = useState<Record<string, CollectorDataTypeChannel[]>>({})
  const [dirtyMap, setDirtyMap] = useState<Record<string, boolean>>({})
  const [savingType, setSavingType] = useState<string | null>(null)
  const [debugState, setDebugState] = useState<DebugState | null>(null)

  const getDraft = (dataType: string): CollectorDataTypeChannel[] =>
    drafts[dataType] ?? dataTypes?.find((item) => item.dataType === dataType)?.channels ?? []

  const change = (dataType: string, channels: CollectorDataTypeChannel[]) => {
    setDrafts((prev) => ({ ...prev, [dataType]: channels }))
    setDirtyMap((prev) => ({ ...prev, [dataType]: true }))
  }

  const save = async (dataType: string) => {
    setSavingType(dataType)
    try {
      await replaceMutation.mutateAsync({
        dataType,
        items: getDraft(dataType).map((item, index) => ({
          channelId: item.channelId,
          priority: index + 1,
        })),
      })
      message.success('渠道优先级已保存')
      setDirtyMap((prev) => ({ ...prev, [dataType]: false }))
    } catch (err) {
      message.error(err instanceof Error ? err.message : '保存失败')
    } finally {
      setSavingType(null)
    }
  }

  const openDebug = (dataType: string, channelId: number, channelName: string) => {
    setDebugState({
      target: {
        channelId,
        channelName,
        supportedDataTypes:
          allChannels?.find((item) => item.id === channelId)?.supportedDataTypes ?? [],
      },
      presetDataType: dataType,
    })
  }

  const collapseItems = useMemo(() => {
    const items = dataTypes ?? []
    const assigned = new Set<string>()
    const pick = (label: string, types: string[]) => {
      const children = items.filter((item) => types.includes(item.dataType))
      children.forEach((child) => assigned.add(child.dataType))
      return { label, children }
    }
    const groups = DATA_TYPE_GROUPS.map(({ label, types }) => pick(label, types))
    const rest = items.filter((item) => !assigned.has(item.dataType))
    if (rest.length > 0) groups.push(pick('其他', rest.map((item) => item.dataType)))

    return groups
      .filter((group) => group.children.length > 0)
      .map(({ label, children }) => ({
        key: label,
        label: `${label}（${children.length}）`,
        children: children.map((item) => (
          <TypePrioritySection
            key={item.dataType}
            dataType={item.dataType}
            channels={getDraft(item.dataType)}
            allChannels={allChannels ?? []}
            dirty={dirtyMap[item.dataType] ?? false}
            saving={savingType === item.dataType}
            onChange={(channels) => change(item.dataType, channels)}
            onSave={() => save(item.dataType)}
            onDebug={(channel) =>
              openDebug(item.dataType, channel.channelId, channel.name)
            }
          />
        )),
      }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataTypes, drafts, dirtyMap, savingType, allChannels])

  return (
    <div>
      {error && (
        <Alert
          message="加载失败"
          description={error instanceof Error ? error.message : '未知错误'}
          type="error"
          showIcon
          className="mb-4"
        />
      )}

      <Alert
        message="说明"
        description={
          <Typography.Text type="secondary">
            展开分组后按数据类型直接配置渠道优先级。任务执行时按顺序尝试：排第一的渠道失败后自动切换到下一个渠道。拖动行或使用上下按钮调整顺序，修改后点击该类型的「保存」。
          </Typography.Text>
        }
        type="info"
        showIcon
        className="mb-4"
      />

      <Collapse items={collapseItems} />
      {collapseItems.length === 0 && !isLoading && (
        <Typography.Text type="secondary">暂无可配置的数据类型。</Typography.Text>
      )}

      <ChannelDebugModal
        open={debugState !== null}
        target={debugState?.target ?? null}
        presetDataType={debugState?.presetDataType ?? null}
        onClose={() => setDebugState(null)}
      />
    </div>
  )
}
