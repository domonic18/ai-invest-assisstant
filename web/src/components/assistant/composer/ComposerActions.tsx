import { PaperClipOutlined, ClearOutlined } from '@ant-design/icons'
import { Button, Tooltip } from 'antd'

interface ComposerActionsProps {
  onClear?: () => void
}

/** Composer 底部动作栏：附件（占位）、清空等扩展入口。 */
export function ComposerActions({ onClear }: ComposerActionsProps) {
  return (
    <div className="flex items-center justify-between px-1 pt-2">
      <div className="flex items-center gap-1">
        <Tooltip title="附件上传（即将上线）">
          <Button
            type="text"
            size="small"
            icon={<PaperClipOutlined />}
            disabled
            className="text-gray-500"
          >
            附件
          </Button>
        </Tooltip>
      </div>
      {onClear && (
        <Button
          type="text"
          size="small"
          icon={<ClearOutlined />}
          onClick={onClear}
          className="text-gray-500 hover:text-gray-300"
        >
          清空对话
        </Button>
      )}
    </div>
  )
}
