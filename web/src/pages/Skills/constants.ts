import type { SkillKind } from '@ai-invest/shared'

export const SKILL_KIND_LABELS: Record<SkillKind, string> = {
  executable: '可执行',
  prompt_only: '提示词',
  doc_only: '方法论',
  custom: '自定义',
}

export const SKILL_KIND_COLORS: Record<SkillKind, string> = {
  executable: 'geekblue',
  prompt_only: 'purple',
  doc_only: 'default',
  custom: 'gold',
}

export const SKILL_MD_PLACEHOLDER = `---
name: 龙头战法每日复盘
description: 聚焦当日龙头股的战法复盘与次日推演
---

## 目标
...

## 步骤
1. ...
`

export const USER_PROMPT_TEMPLATE_HINT =
  '支持 {stock_code}、{trade_date} 等占位符，执行时以实际值替换'
