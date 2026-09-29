/**
 * 观测行图例（执行动态 Tab 与总览页实时决策流共用）：四层判定链路
 * 一句话 + 行内词汇表，Popover 挂在两处卡片 header。
 */
import { QuestionCircleOutlined } from '@ant-design/icons'
import { Popover } from 'antd'

const CHAIN_TEXT =
  '巡检：每分钟对计划标的做确定性比价（L0）→ 触发后模型答三题（L1：动作 / 分时形态 / 盘面支持度）→ 阈值闸门（L2：置信 ≥85% 才真实下单）→ 留痕一行'

const GLOSSARY: Array<[string, string]> = [
  ['心跳行', '未触达触发价的例行巡检，无动作，弱化显示'],
  ['影子', '影子模式：只留痕不下单'],
  ['尾盘强检', '14:50 对止损位强制复核，跌破即卖出'],
  ['依据行', '模型三题的答案（置信 / 盘面支持度 1-5 / 分时形态）与模型版本'],
]

export function ObservationLegend() {
  return (
    <Popover
      placement="bottomRight"
      title="如何读决策流"
      content={
        <div className="max-w-[320px] space-y-2 text-xs leading-relaxed">
          <p className="text-white/70">{CHAIN_TEXT}</p>
          <ul className="space-y-1">
            {GLOSSARY.map(([term, text]) => (
              <li key={term}>
                <span className="font-medium text-white/80">{term}</span>
                <span className="text-white/55">：{text}</span>
              </li>
            ))}
          </ul>
        </div>
      }
    >
      <span className="cursor-pointer text-white/40 transition-colors hover:text-white/70">
        <QuestionCircleOutlined />
      </span>
    </Popover>
  )
}
