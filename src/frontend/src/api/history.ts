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
  values: Array<number | null>
  normalized_values: Array<number | null>
}

export interface HistoryHeatmapPointSeries {
  point_id: string
  original_count: number
  non_null_count: number
  values: Array<number | null>
  normalized_values: Array<number | null>
}

export interface HistoryHeatmapResult {
  timezone: string
  start_time: string
  requested_end_time: string
  actual_end_time: string
  sample_count: number
  requested_sample_count: number
  interval_seconds: number
  times: string[]
  value_range: { min: number; max: number }
  points: HistoryHeatmapPointSeries[]
  correlations: {
    pearson: Array<Array<number | null>>
    spearman: Array<Array<number | null>>
    pair_counts: number[][]
  }
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

export async function queryHistoryHeatmap(payload: HistoryQueryPayload): Promise<HistoryHeatmapResult> {
  const response = await fetch(`${BASE_URL}/history/heatmap`, {
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
  const result = (await response.json()) as ApiResponse<HistoryHeatmapResult>
  if (!result.success || result.code !== 200) throw new Error(result.message || '历史热力图查询失败')
  return result.data
}
