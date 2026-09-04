import { ENDPOINTS } from '@ai-invest/shared'
import type { ApiAuthResponse, ApiUserResponse } from '@ai-invest/shared'

import { apiClient } from './client'
import { mapAuthResponse, mapUser } from './mappers'

export interface LoginCredentials {
  username: string
  password: string
}

export interface RegisterData {
  username: string
  email: string
  password: string
}

export async function login(credentials: LoginCredentials) {
  const params = new URLSearchParams()
  params.append('username', credentials.username)
  params.append('password', credentials.password)

  const response = await apiClient.post<ApiAuthResponse>(ENDPOINTS.auth.login, params, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  return mapAuthResponse(response.data)
}

export async function register(data: RegisterData) {
  const response = await apiClient.post<ApiAuthResponse>(ENDPOINTS.auth.register, data)
  return mapAuthResponse(response.data)
}

export async function fetchCurrentUser() {
  const response = await apiClient.get<ApiUserResponse>(ENDPOINTS.users.me)
  return mapUser(response.data)
}
