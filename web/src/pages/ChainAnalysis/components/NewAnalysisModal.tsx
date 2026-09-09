import { RobotOutlined } from '@ant-design/icons'
import { App, Input, Modal, Space, Tag, Typography } from 'antd'
import { useState } from 'react'

const PRESET_INDUSTRIES = ['半导体', '新能源汽车', '光伏', '锂电池', '人工智能', '创新药']

interface NewAnalysisModalProps {
  open: boolean
  analyzing: boolean
  onConfirm: (industry: string) => void
  onCancel: () => void
}

export function NewAnalysisModal({ open, analyzing, onConfirm, onCancel }: NewAnalysisModalProps) {
  const { message } = App.useApp()
  const [industry, setIndustry] = useState('')

  const handleOk = () => {
    const target = industry.trim()
    if (!target) {
      message.warning('请输入产业链名称')
      return
    }
    setIndustry('')
    onConfirm(target)
  }

  return (
    <Modal
      title="分析新产业链"
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      okButtonProps={{ icon: <RobotOutlined />, loading: analyzing }}
      okText="开始 AI 分析"
      cancelText="取消"
    >
      <div className="space-y-4">
        <Input
          value={industry}
          onChange={(e) => setIndustry(e.target.value)}
          placeholder="输入产业链名称，如：机器人、创新药"
          onPressEnter={handleOk}
        />
        <div className="flex items-center gap-2 flex-wrap">
          <Typography.Text type="secondary" className="text-xs whitespace-nowrap">
            快速选择：
          </Typography.Text>
          <Space size={4} wrap>
            {PRESET_INDUSTRIES.map((item) => (
              <Tag
                key={item}
                className="cursor-pointer hover:border-[#6366f1] hover:text-[#6366f1] transition-colors"
                onClick={() => setIndustry(item)}
              >
                {item}
              </Tag>
            ))}
          </Space>
        </div>
      </div>
    </Modal>
  )
}
