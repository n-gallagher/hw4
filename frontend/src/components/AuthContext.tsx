import { createContext } from 'react'
import type { User } from '../api'

export interface AuthState {
  user: User | null
  loading: boolean
  setUser: (user: User | null) => void
  signOut: () => Promise<void>
}

export const AuthContext = createContext<AuthState | null>(null)
