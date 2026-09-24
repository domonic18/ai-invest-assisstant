import { EyeInvisibleOutlined, RedoOutlined } from '@ant-design/icons'
import {
  Button,
  Card,
  Empty,
  Pagination,
  Popconfirm,
  Radio,
  Select,
  Space,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd'
import { useState } from 'react'

import type { ApiKbImageAsset } from '@ai-invest/shared'

import { useKbImages, useKbSourceMedia, useKbSources } from '@/hooks/useAdminKb'
import { usePatchKbImage, useRedescribeKbImage } from '@/hooks/useAdminKb'

const PAGE_SIZE = 24

const STATUS_FILTERS = [
  { value: null, label: '全部' },
  { value: 'done', label: '已描述' },
  { value: 'pending', label: '待描述' },
  { value: 'failed', label: '描述失败' },
] as const

const STATUS_TAG: Record<string, { color: string; label: string }> = {
  pending: { color: 'default', label: '待描述' },
  processing: { color: 'processing', label: '描述中' },
  done: { color: 'green', label: '已描述' },
  failed: { color: 'red', label: '失败' },
}

function fmtMs(ms: number | null): string {
  if (ms == null) return '?'
  const total = Math.floor(ms / 1000)
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}

function ImageCard({
  image,
  onRedescribe,
  onToggleExcluded,
}: {
  image: ApiKbImageAsset
  onRedescribe: (id: number) => void
  onToggleExcluded: (id: number, excluded: boolean) => void
}) {
  const statusTag = STATUS_TAG[image.describeStatus] ?? { color: 'default', label: image.describeStatus }
  return (
    <Card
      size="small"
      className="overflow-hidden"
      cover={
        <div className="flex h-36 items-center justify-center overflow-hidden bg-black/30">
          {image.thumbUrl ? (
            <img src={image.thumbUrl} alt={image.caption ?? ''} className="max-h-full max-w-full object-contain" />
          ) : (
            <Typography.Text type="secondary">无缩略图</Typography.Text>
          )}
        </div>
      }
    >
      <div className="mb-1 flex flex-wrap items-center gap-1">
        <Tag color={statusTag.color}>{statusTag.label}</Tag>
        {image.describeAttempts > 0 && image.describeStatus !== 'done' && (
          <Tag>重试 {image.describeAttempts}</Tag>
        )}
        {image.indexExcluded && <Tag color="orange">已排除</Tag>}
        <span className="ml-auto text-xs text-[#8a8f98]">{fmtMs(image.startMs)}</span>
      </div>
      <Typography.Paragraph ellipsis={{ rows: 2 }} className="mb-1 text-xs" type="secondary">
        {image.caption || '（无图注）'}
      </Typography.Paragraph>
      {image.visionDescription && (
        <Tooltip title={image.visionDescription}>
          <Typography.Paragraph ellipsis={{ rows: 2 }} className="mb-2 text-xs">
            {image.visionDescription}
          </Typography.Paragraph>
        </Tooltip>
      )}
      <Space size={4}>
        <Popconfirm
          title="重新描述该帧？"
          description="清空现有描述并重置为待描述，下一轮 kb-vision 重新消费（按张计费）。"
          okText="重新描述"
          cancelText="取消"
          onConfirm={() => onRedescribe(image.id)}
          disabled={image.describeStatus === 'pending' || image.describeStatus === 'processing'}
        >
          <Button
            size="small"
            icon={<RedoOutlined />}
            disabled={image.describeStatus === 'pending' || image.describeStatus === 'processing'}
          >
            重新描述
          </Button>
        </Popconfirm>
        {image.indexExcluded ? (
          <Button
            size="small"
            onClick={() => onToggleExcluded(image.id, false)}
          >
            恢复索引
          </Button>
        ) : (
          <Popconfirm
            title="排除该帧？"
            description="排除后不进入知识库检索索引（可随时恢复）。"
            okText="排除"
            cancelText="取消"
            onConfirm={() => onToggleExcluded(image.id, true)}
          >
            <Button size="small" icon={<EyeInvisibleOutlined />}>
              排除
            </Button>
          </Popconfirm>
        )}
      </Space>
    </Card>
  )
}

export function ImagesTab({
  sourceId,
  onSourceChange,
}: {
  sourceId: number | null
  onSourceChange: (id: number | null) => void
}) {
  const { data: sources } = useKbSources()
  const [mediaId, setMediaId] = useState<number | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [page, setPage] = useState(1)

  const { data: medias } = useKbSourceMedia(sourceId)
  const { data: listing, isLoading } = useKbImages(sourceId, mediaId, status, page, PAGE_SIZE)

  const redescribe = useRedescribeKbImage()
  const patchImage = usePatchKbImage()

  const handleRedescribe = async (id: number) => {
    await redescribe.mutateAsync(id)
    message.success('已重置为待描述，下一轮 kb-vision 重新生成')
  }

  const handleToggleExcluded = async (id: number, excluded: boolean) => {
    await patchImage.mutateAsync({ imageId: id, data: { indexExcluded: excluded } })
    message.success(excluded ? '已排除，不进入检索索引' : '已恢复，将随批次 E 进入检索索引')
  }

  const episodeOptions = (medias ?? [])
    .filter((m) => m.mediaKind === 'video')
    .map((m) => ({ value: m.id, label: m.episodeNo ? `第 ${m.episodeNo} 集 ${m.title}` : m.title }))

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Select
          value={sourceId ?? undefined}
          onChange={(v) => {
            onSourceChange(v ?? null)
            setMediaId(null)
            setPage(1)
          }}
          placeholder="选择知识库"
          style={{ width: 280 }}
          options={(sources ?? []).map((s) => ({
            value: s.id,
            label: `${s.name}（${s.sourceType === 'course' ? '课程' : '电子书'}）`,
          }))}
        />
        <Select
          value={mediaId ?? undefined}
          onChange={(v) => {
            setMediaId(v ?? null)
            setPage(1)
          }}
          allowClear
          placeholder="全部集数"
          style={{ width: 220 }}
          options={episodeOptions}
        />
        <Space wrap>
          {STATUS_FILTERS.map((f) => (
            <Radio.Button
              key={f.value ?? 'all'}
              checked={status === f.value}
              onClick={() => {
                setStatus(f.value)
                setPage(1)
              }}
            >
              {f.label}
            </Radio.Button>
          ))}
        </Space>
        <span className="ml-auto text-xs text-[#8a8f98]">
          共 {listing?.total ?? 0} 张
        </span>
      </div>

      {!sourceId ? (
        <Empty description="请先选择知识库" />
      ) : !listing?.items.length ? (
        <Empty description={isLoading ? '加载中…' : '暂无图片资产（视频选帧由 kb-vision 定时任务生成）'} />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {listing.items.map((image) => (
              <ImageCard
                key={image.id}
                image={image}
                onRedescribe={handleRedescribe}
                onToggleExcluded={handleToggleExcluded}
              />
            ))}
          </div>
          <div className="mt-4 flex justify-end">
            <Pagination
              current={page}
              pageSize={PAGE_SIZE}
              total={listing.total}
              onChange={setPage}
              showSizeChanger={false}
            />
          </div>
        </>
      )}
    </div>
  )
}
