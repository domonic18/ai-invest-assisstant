/** User roles. */
export const UserRole = {
  ADMIN: 'admin',
  USER: 'user',
  ANALYST: 'analyst',
} as const

export type UserRole = (typeof UserRole)[keyof typeof UserRole]
