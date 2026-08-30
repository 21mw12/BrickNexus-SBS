import { BASE_URL } from '../config'
import { storePageCodes, clearPageCodes } from '../utils/permission'

export interface LoginPayload {
  account: string
  password: string
}

// 后端统一响应的外层结构
export interface ApiResponse<T> {
  success: boolean
  code: number
  message: string
  data: T
}

// 登录成功后 data 字段的内容
export interface LoginData {
  token: string
  token_type: string
  expires_in: number
  user_id: string
  role_id: string
  account: string
  nickname: string
  page_codes: string[]  // 页面权限码列表
}

/**
 * 登录
 */
export async function login(payload: LoginPayload): Promise<LoginData> {
  const response = await fetch(`${BASE_URL}/user/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(errorText || '登录失败')
  }

  const apiResponse = (await response.json()) as ApiResponse<LoginData>

  // 检查业务状态码
  if (!apiResponse.success || apiResponse.code !== 200) {
    throw new Error(apiResponse.message || '登录失败')
  }

  const loginData = apiResponse.data

  // 确保 token 存在
  if (!loginData.token) {
    throw new Error('服务器返回的 token 为空')
  }

  // 存储 token 和用户信息
  localStorage.setItem('auth_token', loginData.token)
  localStorage.setItem('auth_user', JSON.stringify({
    nickname: loginData.nickname,
    account: loginData.account,
    userId: loginData.user_id,
  }))

  // 存储页面权限：root 账号拥有全部权限，其他账号使用 API 返回的 page_codes
  if (loginData.account === 'root') {
    storePageCodes(['*'])
  } else if (loginData.page_codes && loginData.page_codes.length > 0) {
    storePageCodes(loginData.page_codes)
  } else {
    storePageCodes([])
  }

  return loginData
}

/**
 * 登出
 * 无论后端接口是否返回错误，都会清除本地存储。
 * 如果后端返回非 2xx（例如 token 不存在时返回 404），仅记录日志，不影响前端登出行为。
 */
export async function logout() {
  let token = localStorage.getItem('auth_token')
  
  if (!token || token === 'undefined' || token === 'null') {
    clearLocalAuth()
    return
  }

  try {
    const response = await fetch(`${BASE_URL}/user/logout`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'application/json',
      },
    })

    // 后端 logout 可能也返回包装结构，但无论成功与否都清除本地存储
    if (!response.ok) {
      console.debug('登出接口返回非 2xx', response.status)
    }
  } catch (error) {
    console.warn('登出网络错误', error)
  } finally {
    clearLocalAuth()
  }
}

/**
 * 仅清除本地存储中的认证信息
 */
function clearLocalAuth(): void {
  localStorage.removeItem('auth_token')
  localStorage.removeItem('auth_user')
  clearPageCodes()
}

/**
 * 获取当前登录的用户信息（从 localStorage 中读取）
 */
export function getCurrentUser() {
  const raw = localStorage.getItem('auth_user')
  if (!raw) return null
  try {
    return JSON.parse(raw) as { nickname: string; account: string; userId: string }
  } catch {
    return null
  }
}

/**
 * 获取当前存储的 token
 */
export function getToken(): string | null {
  const token = localStorage.getItem('auth_token')
  if (token && token !== 'undefined' && token !== 'null') {
    return token
  }
  return null
}
