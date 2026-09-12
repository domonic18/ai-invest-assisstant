import { ArrowUpOutlined, DeleteOutlined, EnterOutlined } from '@ant-design/icons'
import { AutoComplete, Button, Input } from 'antd'

interface ScreeningSearchBoxProps {
  value: string
  onChange: (value: string) => void
  /** 提交问句（回车 / 点击箭头 / 点选历史） */
  onSubmit: (query: string) => void
  loading: boolean
  /** 历史问句（最新在前）；为空时不弹下拉 */
  history: string[]
  onClearHistory: () => void
  /** 初始态居中大盒；结果态顶部普通盒 */
  hero?: boolean
}

/** 问财式搜索框：圆角大盒 + 无边框输入 + 圆形箭头提交钮；下拉为最近问句历史。 */
export function ScreeningSearchBox({
  value,
  onChange,
  onSubmit,
  loading,
  history,
  onClearHistory,
  hero = false,
}: ScreeningSearchBoxProps) {
  const submit = () => {
    const trimmed = value.trim()
    if (trimmed) onSubmit(trimmed)
  }

  const options = history.map((item) => ({
    value: item,
    label: (
      <div className="flex items-center gap-2 py-0.5">
        <EnterOutlined className="shrink-0 text-blue-400" />
        <span className="truncate">{item}</span>
      </div>
    ),
  }))

  return (
    <div
      className={`flex items-end gap-2 rounded-2xl border border-white/10 bg-white/[0.03] p-3 ${
        hero ? 'shadow-[0_8px_32px_rgba(0,0,0,0.35)]' : ''
      }`}
    >
      <AutoComplete
        className="flex-1"
        value={value}
        onChange={onChange}
        options={options}
        filterOption={false}
        popupMatchSelectWidth={undefined}
        onSelect={(selected: string) => {
          onChange(selected)
          onSubmit(selected)
        }}
        dropdownRender={(menu) => (
          <div>
            <div className="flex items-center justify-between border-b border-white/10 px-3 py-1.5">
              <span className="text-sm font-semibold">历史问句</span>
              <Button type="text" size="small" icon={<DeleteOutlined />} onClick={onClearHistory}>
                清空
              </Button>
            </div>
            {menu}
          </div>
        )}
      >
        <Input
          variant="borderless"
          size="large"
          maxLength={500}
          placeholder="请输入您的筛选条件，多个条件用分号隔开"
          onPressEnter={submit}
        />
      </AutoComplete>
      <Button
        type="primary"
        shape="circle"
        size="large"
        icon={<ArrowUpOutlined />}
        loading={loading}
        disabled={!value.trim()}
        onClick={submit}
      />
    </div>
  )
}
