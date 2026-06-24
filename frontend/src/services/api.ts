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

// Add response interceptor for error handling
api.interceptors.response.use(
  response => response,
  error => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)
