import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../services/api'

const TOKEN_KEY = 'auth.token'

interface AuthUser {
  id: string
  username: string
  display_name: string
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const user = ref<AuthUser | null>(null)
  const loginError = ref<string | null>(null)
  const loading = ref<boolean>(false)

  const isAuthenticated = computed(() => !!token.value && !!user.value)

  const setToken = (t: string | null) => {
    token.value = t
    if (t) {
      localStorage.setItem(TOKEN_KEY, t)
    } else {
      localStorage.removeItem(TOKEN_KEY)
    }
  }

  const login = async (username: string, password: string): Promise<boolean> => {
    loading.value = true
    loginError.value = null
    try {
      const response = await api.post('/api/auth/login', { username, password })
      const data = response.data?.data
      if (data?.token && data?.user) {
        setToken(data.token)
        user.value = data.user
        return true
      }
      loginError.value = 'Unexpected server response'
      return false
    } catch (error: any) {
      const msg = error?.response?.data?.message || 'Login failed'
      loginError.value = msg
      return false
    } finally {
      loading.value = false
    }
  }

  const logout = () => {
    setToken(null)
    user.value = null
  }

  const checkAuth = async (): Promise<boolean> => {
    if (!token.value) {
      return false
    }
    loading.value = true
    try {
      const response = await api.get('/api/auth/me', {
        headers: { Authorization: `Bearer ${token.value}` }
      })
      const data = response.data?.data
      if (data?.id) {
        user.value = data
        return true
      }
      logout()
      return false
    } catch {
      logout()
      return false
    } finally {
      loading.value = false
    }
  }

  return {
    token,
    user,
    loginError,
    loading,
    isAuthenticated,
    login,
    logout,
    checkAuth
  }
})
