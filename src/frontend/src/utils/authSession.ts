import { clearPageCodes } from './permission'

let redirecting = false

export function clearAuthSession() {
  localStorage.removeItem('auth_token')
  localStorage.removeItem('auth_user')
  clearPageCodes()
}

export function redirectToLogin() {
  clearAuthSession()
  if (redirecting || window.location.pathname === '/login') return
  redirecting = true
  window.location.replace('/login')
}

export function isTokenExpired(token: string | null): boolean {
  if (!token || token === 'undefined' || token === 'null') return true
  try {
    const payload = token.split('.')[1]
    if (!payload) return false
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/')
    const data = JSON.parse(atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')))
    return typeof data.exp === 'number' && Date.now() >= data.exp * 1000
  } catch {
    return false
  }
}

export function installAuthFetchInterceptor() {
  const nativeFetch = window.fetch.bind(window)
  window.fetch = async (...args: Parameters<typeof fetch>) => {
    const hadToken = !!localStorage.getItem('auth_token')
    const response = await nativeFetch(...args)
    let unauthorized = response.status === 401
    if (!unauthorized && hadToken && (response.headers.get('content-type') || '').includes('application/json')) {
      try {
        const body = await response.clone().json()
        unauthorized = body?.code === 401 || body?.code === 'unauthorized'
      } catch { /* 响应体仍交给业务请求处理 */ }
    }
    if (hadToken && unauthorized) redirectToLogin()
    return response
  }
}
