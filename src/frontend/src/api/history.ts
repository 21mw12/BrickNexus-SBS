import { BASE_URL } from '../config'
import { getToken } from './auth'

export interface HistoryQueryPayload {
  point_ids: string[]
  start_time: string
  end_time: string
  sample_count: number
}

export interface HistoryPointSeries {
  point_id: string
  original_count: number
  returned_count: number
  downsampled: boolean
  times: string[]
  values: number[]
}

export interface HistoryQueryResult {
  timezone: string
  start_time: string
  requested_end_time: string
  actual_end_time: string
  sample_count: number
  points: HistoryPointSeries[]
}

interface ApiResponse<T> { success: boolean; code: number; message: string; data: T }

export async function queryHistory(payload: HistoryQueryPayload): Promise<HistoryQueryResult> {
  const response = await fetch(`${BASE_URL}/history/query`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${getToken()}`,
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    try { const body = await response.json(); throw new Error(body?.message || `查询失败（${response.status}）`) }
    catch (error) { if (error instanceof Error) throw error; throw new Error(`查询失败（${response.status}）`) }
  }
  const result = (await response.json()) as ApiResponse<HistoryQueryResult>
  if (!result.success || result.code !== 200) throw new Error(result.message || '历史数据查询失败')
  return result.data
}
