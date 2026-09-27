export interface MovingAverageConfig {
  period: number
  color: string
  enabled: boolean
}

export interface UserSettings {
  maConfigs: MovingAverageConfig[]
  /** 工作台/宏观页展示的跟踪指数代码（全球指标）；undefined/null = 全部显示，[] = 全部不显示 */
  trackedIndexCodes?: string[] | null
}

export interface User {
  id: string
  username: string
  email: string
  isAdmin: boolean
}

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
}

export interface AuthResponse {
  accessToken: string
  user: User
}

export interface ApiRegisterRequest {
  username: string
  email: string
  password: string
  applicationNote?: string
}

export interface ApiMovingAverageConfig {
  period: number
  color: string
  enabled: boolean
}

export interface ApiUserSettings {
  maConfigs: ApiMovingAverageConfig[]
}

export interface ApiUserSettingsUpdateRequest {
  maConfigs: ApiMovingAverageConfig[]
}

export interface ApiUserResponse {
  id: number
  username: string
  email: string
  role: string
  isActive: boolean
  status: string
  applicationNote: string | null
  rejectReason: string | null
  lastLoginAt: string | null
  createdAt: string
}

export interface ApiUserUpdateRequest {
  email: string
}

export interface ApiPasswordChangeRequest {
  currentPassword: string
  newPassword: string
}

export interface ApiAuthResponse {
  accessToken: string
  tokenType: string
  user: ApiUserResponse
}

export interface ApiWatchlistItemCreate {
  stockCode: string
  tags?: string[]
  groupId?: number
}

export interface ApiWatchlistItemResponse {
  id: number
  stockCode: string
  tags: string[] | null
  groupId: number
  createdAt: string
}

export interface ApiWatchlistGroupCreate {
  name: string
  aiReviewEnabled?: boolean
}

export interface ApiWatchlistGroupUpdate {
  name?: string
  aiReviewEnabled?: boolean
}

export interface ApiWatchlistGroupResponse {
  id: number
  name: string
  sortOrder: number
  isDefault: boolean
  aiReviewEnabled: boolean
  createdAt: string
}

export interface ApiWatchlistGroupWithItemsResponse extends ApiWatchlistGroupResponse {
  items: ApiWatchlistItemResponse[]
}

export interface ApiWatchlistGroupReorderRequest {
  groupIds: number[]
}

export interface ApiWatchlistItemMoveRequest {
  groupId: number
}

export interface ApiWatchlistScreenshotRecognitionItem {
  stockCode: string
  stockName: string | null
  confidence: number | null
  valid: boolean
  matchedName: string | null
}

export interface ApiWatchlistScreenshotRecognitionResponse {
  items: ApiWatchlistScreenshotRecognitionItem[]
}

export interface ApiWatchlistBatchItemCreate {
  stockCode: string
  tags?: string[]
}

export interface ApiWatchlistBatchCreate {
  items: ApiWatchlistBatchItemCreate[]
  groupId?: number
  newGroupName?: string
}

export interface ApiWatchlistBatchDuplicatedItem {
  stockCode: string
  groupId: number | null
  groupName: string | null
}

export interface ApiWatchlistBatchResponse {
  created: ApiWatchlistItemResponse[]
  duplicated: ApiWatchlistBatchDuplicatedItem[]
  invalid: string[]
}
