import { createContext, useContext } from 'react'
import type { Me } from './api/types'

export interface AuthValue {
  user: Me | null
  refresh: () => Promise<void>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthValue>({
  user: null,
  refresh: async () => {},
  logout: async () => {},
})

export function useAuth() {
  return useContext(AuthContext)
}

export function useIsOrgAdmin(): boolean {
  const { user } = useAuth()
  return (user?.memberships ?? []).some((m) => m.role === 'ADMIN')
}

export function useIsOrgStaff(): boolean {
  const { user } = useAuth()
  return (user?.memberships ?? []).length > 0
}
