/**
 * echarts-for-react core 版包装：绑定 echarts.ts 的按需注册实例。
 * 全站图表一律经本组件引入（替换 `echarts-for-react` 直引），props/ref
 * 契约不变（ref 拿到的实例类型为 core 类，与原类组件同形）。
 */
import { forwardRef } from 'react'
import type { ComponentProps } from 'react'

import ReactEChartsCore from 'echarts-for-react/lib/core'
import type EChartsReactCore from 'echarts-for-react/lib/core'

import { echarts } from './echarts'

type Props = Omit<ComponentProps<typeof ReactEChartsCore>, 'echarts'>

const ReactECharts = forwardRef<EChartsReactCore, Props>((props, ref) => (
  <ReactEChartsCore ref={ref} {...props} echarts={echarts} />
))

export default ReactECharts
