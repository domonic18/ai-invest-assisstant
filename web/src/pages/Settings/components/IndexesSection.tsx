/** 跟踪指数 section：工作台/宏观指数页展示指标勾选。 */

import { Card } from 'antd'

import { TrackedIndexSettings } from './TrackedIndexSettings'
import { HintBox } from './SettingHints'

export function IndexesSection() {
  return (
    <Card
      variant="borderless"
      title="跟踪指数"
      extra={<span className="text-xs text-[#5c616e]">默认显示全部</span>}
    >
      <TrackedIndexSettings />
      <HintBox>
        控制工作台「市场指数」与宏观指数页展示哪些指标；A 股指数 / ETF
        支持自定义添加（历史行情自动回填），全球指标暂限内置清单。保存在<b>服务端</b>（随账号漫游）；全部勾选即恢复默认。
      </HintBox>
    </Card>
  )
}
