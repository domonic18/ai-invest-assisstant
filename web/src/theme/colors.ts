/**
 * 设计 token 从 @ai-invest/shared 再导出：保持 web 侧既有导入路径
 * （`@/theme/colors`、tailwind.config.js）不变，色板源头在 shared 包。
 */

export {
  ChartColors,
  panelColors,
  semanticColors,
  type PanelColorKey,
} from '@ai-invest/shared'
