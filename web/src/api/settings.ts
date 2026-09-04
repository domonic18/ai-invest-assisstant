import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiUserSettings,
  ApiUserSettingsUpdateRequest,
  UserSettings,
} from '@ai-invest/shared'

import { apiClient } from './client'
import { mapUserSettings } from './mappers'
import { normalizeHexColor } from '@/utils/color'

export async function fetchUserSettings(): Promise<UserSettings> {
  const response = await apiClient.get<ApiUserSettings>(ENDPOINTS.users.meSettings)
  return mapUserSettings(response.data)
}

export async function updateUserSettings(settings: UserSettings): Promise<UserSettings> {
  const body: ApiUserSettingsUpdateRequest = {
    ma_configs: settings.maConfigs.map((item) => ({
      period: Math.round(item.period),
      color: normalizeHexColor(item.color),
      enabled: item.enabled,
    })),
  }
  const response = await apiClient.put<ApiUserSettings>(ENDPOINTS.users.meSettings, body)
  return mapUserSettings(response.data)
}
