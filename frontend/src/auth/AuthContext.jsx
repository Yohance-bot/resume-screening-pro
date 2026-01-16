import React, { createContext, useContext, useState, useEffect } from 'react'
import { login as loginService, logout as logoutService, me } from '../services/auth'

const AuthContext = createContext()

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const refresh = async () => {
    try {
      const result = await me()
      if (result.authenticated) {
        setUser(result.user)
      } else {
        setUser(null)
      }
    } catch (error) {
      console.error('Auth check failed:', error)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }

  const login = async (email, password) => {
    try {
      const result = await loginService(email, password)
      setUser(result.user)
      return result
    } catch (error) {
      throw error
    }
  }

  const logout = async () => {
    try {
      await logoutService()
      setUser(null)
    } catch (error) {
      console.error('Logout failed:', error)
      // Still clear user state even if logout fails
      setUser(null)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  const value = {
    user,
    loading,
    login,
    logout,
    refresh,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
