import { BASE_URL } from '../config'
import { getToken } from './auth'

export interface DashboardPageItem {
  key: string
  item: string
  description: string
  usage: string
}

export interface DashboardAssetStatistic {
  enabled_total: number
  online_count?: number
}

export interface DashboardStatistics {
  user_count: number
  request_count: number
  control_count: number
  rule_count: number
  building: DashboardAssetStatistic
  floor: DashboardAssetStatistic
  room: DashboardAssetStatistic
  terminal: DashboardAssetStatistic
  sensor: DashboardAssetStatistic
}

export interface DashboardOverview {
  page: DashboardPageItem[]
  statistics: DashboardStatistics
}

interface ApiResponse<T> {
  success: boolean
  code: number
  message: string
  data: T
}

export async function fetchDashboardOverview(): Promise<DashboardOverview> {
  const response = await fetch(`${BASE_URL}/dashboard/overview`, {
    headers: {
      Authorization: `Bearer ${getToken()}`,
      Accept: 'application/json',
    },
  })
  if (!response.ok) {
    let message = `获取看板概览失败（${response.status}）`
    try { message = (await response.json())?.message || message } catch { /* 非 JSON 错误响应 */ }
    throw new Error(message)
  }
  const result = (await response.json()) as ApiResponse<DashboardOverview>
  if (!result.success || result.code !== 200) throw new Error(result.message || '获取看板概览失败')
  return result.data
}
