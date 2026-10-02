/**
 * echarts 按需注册单一入口：全站图表经 ReactECharts 包装消费本模块，
 * 禁止直接 `import * as echarts from 'echarts'`（拉全量 ~1MB 进 charts chunk）。
 * 新增图表类型/组件时在此补注册，漏注册的 series 静默不渲染。
 */
import { BarChart, CandlestickChart, LineChart, ScatterChart } from 'echarts/charts'
import {
  AxisPointerComponent,
  DataZoomComponent,
  DatasetComponent,
  GraphicComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  LineChart,
  BarChart,
  CandlestickChart,
  ScatterChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  DataZoomComponent,
  MarkLineComponent,
  GraphicComponent,
  AxisPointerComponent,
  DatasetComponent,
  CanvasRenderer,
])

export { echarts }
