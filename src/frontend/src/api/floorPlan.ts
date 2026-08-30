import { BASE_URL } from '../config'
import { getToken } from './auth'

export interface FloorRoomRegion {
  room_id: string
  room_name: string
  x: number
  y: number
  width: number
  height: number
}

export interface FloorPlan {
  floor_id: string
  image_name: string
  image_width: number
  image_height: number
  image_type: string
  image_url: string
  regions: FloorRoomRegion[]
}

interface ApiResponse<T> {
  success: boolean
  code: number
  message: string
  data: T
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json()
    return body?.message || `请求失败（${response.status}）`
  } catch {
    return `请求失败（${response.status}）`
  }
}

function headers(json = false): HeadersInit {
  return {
    Authorization: `Bearer ${getToken()}`,
    Accept: 'application/json',
    ...(json ? { 'Content-Type': 'application/json' } : {}),
  }
}

async function unwrap<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error(await errorMessage(response))
  const result = (await response.json()) as ApiResponse<T>
  if (!result.success || result.code !== 200) throw new Error(result.message || '请求失败')
  return result.data
}

export async function fetchFloorPlan(floorId: string): Promise<FloorPlan> {
  return unwrap(await fetch(`${BASE_URL}/floor-plans/${encodeURIComponent(floorId)}`, {
    headers: headers(),
  }))
}

/** 图片接口需要 Bearer Token，先读取为 Blob，再交给 img 显示。 */
export async function fetchFloorPlanImage(floorId: string): Promise<Blob> {
  const response = await fetch(`${BASE_URL}/floor-plans/${encodeURIComponent(floorId)}/image`, {
    headers: headers(),
  })
  if (!response.ok) throw new Error(await errorMessage(response))
  return response.blob()
}

export async function uploadFloorPlan(floorId: string, image: File): Promise<FloorPlan> {
  const form = new FormData()
  form.append('image', image)
  return unwrap(await fetch(`${BASE_URL}/floor-plans/${encodeURIComponent(floorId)}/image`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${getToken()}`, Accept: 'application/json' },
    body: form,
  }))
}

export async function saveFloorPlanRegions(
  floorId: string,
  regions: Pick<FloorRoomRegion, 'room_id' | 'x' | 'y' | 'width' | 'height'>[],
): Promise<FloorPlan> {
  return unwrap(await fetch(`${BASE_URL}/floor-plans/${encodeURIComponent(floorId)}/regions`, {
    method: 'PUT',
    headers: headers(true),
    body: JSON.stringify({ regions }),
  }))
}

export async function deleteFloorPlan(floorId: string): Promise<void> {
  await unwrap<{ ok: boolean }>(await fetch(`${BASE_URL}/floor-plans/${encodeURIComponent(floorId)}`, {
    method: 'DELETE',
    headers: headers(),
  }))
}
