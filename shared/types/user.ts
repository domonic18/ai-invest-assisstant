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
