import { BASE_URL } from '../config'
import { getToken, type ApiResponse } from './auth'

export interface PointDefinition {
  point_id: string
  point_name: string
  point_unit: string
  point_description: string | null
}

export interface CreatePointPayload {
  point_name: string
  point_unit: string
  point_description?: string | null
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${getToken()}`, Accept: 'application/json', ...(init?.body ? { 'Content-Type': 'application/json' } : {}), ...init?.headers },
  })
  if (!response.ok) {
    try { const body = await response.json(); throw new Error(body?.message || `请求失败（${response.status}）`) }
    catch (error) { if (error instanceof Error) throw error; throw new Error(`请求失败（${response.status}）`) }
  }
  const result = (await response.json()) as ApiResponse<T>
  if (!result.success || result.code !== 200) throw new Error(result.message || '请求失败')
  return result.data
}

export async function fetchPointPage(page = 1, limit = 20) {
  const data = await request<{ total: number; items: PointDefinition[] }>(`/points/list?page=${page}&limit=${limit}`)
  return { data: data.items, total: data.total }
}

export function fetchPointDetail(pointId: string) {
  return request<PointDefinition>(`/points/find/${encodeURIComponent(pointId)}`)
}

export function createPoint(payload: CreatePointPayload) {
  return request<PointDefinition>('/points/add', { method: 'POST', body: JSON.stringify(payload) })
}

export function editPointDescription(pointId: string, pointDescription: string | null) {
  return request<PointDefinition>(`/points/edit/${encodeURIComponent(pointId)}`, { method: 'POST', body: JSON.stringify({ point_description: pointDescription }) })
}

export async function deletePoint(pointId: string) {
  await request<{ ok: boolean }>(`/points/drop/${encodeURIComponent(pointId)}`)
}
