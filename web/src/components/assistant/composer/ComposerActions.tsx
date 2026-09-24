import { DatabaseOutlined, PaperClipOutlined } from '@ant-design/icons'
import { Button, Switch, Tooltip } from 'antd'

import { useAssistantStore } from '@/stores/assistant'

/** Composer 底部动作栏：知识库开关、附件（占位）等扩展入口。 */
export function ComposerActions() {
  const useKb = useAssistantStore((state) => state.useKb)
  const setUseKb = useAssistantStore((state) => state.setUseKb)

  return (
    <div className="flex items-center justify-between px-1 pt-2">
      <div className="flex items-center gap-2">
        <Tooltip title="关闭后对话不检索投资课程知识库">
          <label className="flex cursor-pointer items-center gap-1.5 text-xs text-gray-400">
            <DatabaseOutlined className={useKb ? 'text-sky-400' : undefined} />
            知识库
            <Switch size="small" checked={useKb} onChange={setUseKb} />
          </label>
        </Tooltip>
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
    </div>
  )
}
