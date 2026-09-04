import type {
  ApiAuthResponse,
  ApiUserResponse,
  ApiUserSettings,
} from '@ai-invest/shared'
import type { AuthResponse, MovingAverageConfig, User, UserSettings } from '@ai-invest/shared'

export function mapUser(dto: ApiUserResponse): User {
  return {
    id: String(dto.id),
    username: dto.username,
    email: dto.email,
    isAdmin: dto.role === 'admin',
  }
}

export function mapAuthResponse(dto: ApiAuthResponse): AuthResponse {
  return {
    accessToken: dto.access_token,
    user: mapUser(dto.user),
  }
}

export function mapUserSettings(dto: ApiUserSettings): UserSettings {
  return {
    maConfigs: dto.ma_configs.map(
      (item): MovingAverageConfig => ({
        period: item.period,
        color: item.color,
        enabled: item.enabled,
      })
    ),
  }
}
