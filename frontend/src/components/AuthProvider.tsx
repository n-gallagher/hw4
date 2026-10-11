import { useEffect, useState, type ReactNode } from 'react'
import { getMe, logout, type User } from '../api'
import { AuthContext } from './AuthContext'

export default function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  // The session lives in an HttpOnly cookie, so ask the server who is logged in.
  useEffect(() => {
    getMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  const signOut = async () => {
    await logout()
    setUser(null)
  }

  return <AuthContext.Provider value={{ user, loading, setUser, signOut }}>{children}</AuthContext.Provider>
}
