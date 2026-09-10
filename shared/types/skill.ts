/** Skill 广场与用户技能类型：camelCase wire。 */

/** 技能形态：builtin 三态 + 用户自定义。 */
export type SkillKind = 'executable' | 'prompt_only' | 'doc_only' | 'custom'

/** 业务场景分类（技能广场 Tab），与后端 registry SCENARIO_LABELS 对齐。 */
export type SkillScenario = 'market' | 'stock' | 'chain' | 'report' | 'news' | 'custom'

/** 场景编码有序清单（Tab 顺序）。 */
export const SKILL_SCENARIOS = ['market', 'stock', 'chain', 'report', 'news'] as const

/** 场景中文名（唯一真相源，前端禁止另处硬编码）。 */
export const SKILL_SCENARIO_LABELS: Record<SkillScenario, string> = {
  market: '大盘与情绪',
  stock: '个股分析',
  chain: '产业链',
  report: '财报与研报',
  news: '资讯处理',
  custom: '自定义',
}

/** 能力徽标文案（kind → 展示语义）。 */
export const SKILL_KIND_BADGES: Record<SkillKind, { label: string; color: string }> = {
  executable: { label: '自动化·定时', color: 'blue' },
  prompt_only: { label: '对话调用', color: 'green' },
  doc_only: { label: '方法论', color: 'orange' },
  custom: { label: '自定义技能', color: 'purple' },
}

/** custom skill 结构化输出分区声明。 */
export interface ApiCustomSkillSection {
  key: string
  title: string
  requirements?: string
}

/** custom skill 定义（skill.customDefinition 的 wire 形态）。 */
export interface ApiCustomSkillDefinition {
  skillMd: string
  systemPrompt: string
  userPromptTemplate?: string | null
  sections?: ApiCustomSkillSection[]
  allowedTools?: string[]
}

/** 广场/我的技能列表项。 */
export interface ApiSkillItem {
  skillId: string
  label: string
  kind: SkillKind
  scenario: SkillScenario | null
  isBuiltin: boolean
  published: boolean
  installed: boolean
  enabled: boolean | null
  description: string | null
}

/** GET /skills 响应：广场（可安装）+ 我的（已安装与本人 custom）。 */
export interface ApiSkillSquareResponse {
  available: ApiSkillItem[]
  mine: ApiSkillItem[]
}

/** 技能详情。 */
export interface ApiSkillResponse {
  skillId: string
  label: string
  kind: SkillKind
  scenario: SkillScenario | null
  isBuiltin: boolean
  published: boolean
  description: string | null
  ownerUserId: number | null
  version: number
  customDefinition: ApiCustomSkillDefinition | null
  createdAt: string
  updatedAt: string
}

/** 安装/卸载后的用户技能状态。 */
export interface ApiUserSkillResponse {
  skillId: string
  installed: boolean
  enabled: boolean
}

/** 创建 custom skill 请求。 */
export interface ApiCustomSkillCreateRequest {
  skillId: string
  label: string
  description?: string | null
  customDefinition: ApiCustomSkillDefinition
}

/** 更新 custom skill 请求（缺省字段不变）。 */
export interface ApiCustomSkillUpdateRequest {
  label?: string
  description?: string | null
  customDefinition?: ApiCustomSkillDefinition
}

/** 技能包内单个文件（builtin 读镜像目录；custom 由配置合成虚拟文件）。 */
export interface ApiSkillFile {
  path: string
  size: number
  content: string
}

/** POST /skills/analyze 响应：压缩包解析出的表单预填建议。 */
export interface ApiSkillAnalyzeResponse {
  skillId: string
  label: string
  description: string | null
  skillMd: string
  systemPrompt: string
  userPromptTemplate: string | null
  sections?: ApiCustomSkillSection[]
  allowedTools?: string[]
  fileIndex: { path: string; size: number }[]
}

/** GET /skills/{id}/files 响应：synthetic=true 表示由 DB 配置合成，非镜像文件。 */
export interface ApiSkillFilesResponse {
  skillId: string
  isBuiltin: boolean
  synthetic: boolean
  files: ApiSkillFile[]
}
