/** Skill 广场与用户技能类型：camelCase wire。 */

/** 技能形态：builtin 三态 + 用户自定义。 */
export type SkillKind = 'executable' | 'prompt_only' | 'doc_only' | 'custom'

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

/** GET /skills/{id}/files 响应：synthetic=true 表示由 DB 配置合成，非镜像文件。 */
export interface ApiSkillFilesResponse {
  skillId: string
  isBuiltin: boolean
  synthetic: boolean
  files: ApiSkillFile[]
}
