import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiUserSettings,
  ApiUserSettingsUpdateRequest,
  UserSettings,
} from '@ai-invest/shared'

import { apiClient } from './client'
import { mapUserSettings } from './mappers'

export async function fetchUserSettings(): Promise<UserSettings> {
  const response = await apiClient.get<ApiUserSettings>(ENDPOINTS.users.meSettings)
  return mapUserSettings(response.data)
}

export async function updateUserSettings(settings: UserSettings): Promise<UserSettings> {
  const body: ApiUserSettingsUpdateRequest = {
    ma_configs: settings.maConfigs.map((item) => ({
      period: item.period,
      color: item.color,
      enabled: item.enabled,
    })),
  }
  const response = await apiClient.put<ApiUserSettings>(ENDPOINTS.users.meSettings, body)
  return mapUserSettings(response.data)
}
