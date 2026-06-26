import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000'
const API_TIMEOUT = parseInt(import.meta.env.VITE_API_TIMEOUT || '30000')

export const api = axios.create({
  baseURL: API_URL,
  timeout: API_TIMEOUT,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Attach Bearer token to every request when available.
api.interceptors.request.use(config => {
  const token = localStorage.getItem('auth.token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle 401 globally — clear token and reload to show login page.
api.interceptors.response.use(
  response => response,
  error => {
    if (error?.response?.status === 401) {
      localStorage.removeItem('auth.token')
      window.location.reload()
    }
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)
