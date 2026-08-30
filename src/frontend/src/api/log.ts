import { BASE_URL } from '../config'
import { getToken } from './auth'

export type LogType = 'rule_action' | 'rule_operation'
export type LogLevel = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL'

export interface SystemLog {
  id: string
  type: LogType
  level: LogLevel
  operator: string
  content: string
  time: string
}

export interface LogQuery {
  type?: LogType
  level?: LogLevel
  operator?: string
  time?: string
}

interface ApiResponse<T> {
  success: boolean
  code: number
  message: string
  data: T
}

export async function fetchLogs(page: number, limit: number, query: LogQuery) {
  const response = await fetch(`${BASE_URL}/logs/list?page=${page}&limit=${limit}`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${getToken()}`,
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(query),
  })
  if (!response.ok) {
    let message = `查询日志失败（${response.status}）`
    try { message = (await response.json())?.message || message } catch { /* 非 JSON 错误响应 */ }
    throw new Error(message)
  }
  const result = (await response.json()) as ApiResponse<{ total: number; items: SystemLog[] }>
  if (!result.success || result.code !== 200) throw new Error(result.message || '查询日志失败')
  return { data: result.data.items, total: result.data.total }
}
