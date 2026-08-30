import { BASE_URL } from '../config'
import { getToken, type ApiResponse } from './auth'

// ==================== 工具 ====================

async function extractMessage(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (body?.message) return body.message
  } catch {}
  try {
    return await response.text()
  } catch {
    return `请求失败（状态码：${response.status}）`
  }
}

// ==================== 类型 ====================

export interface ModelPointItem {
  point_id: string
  point_name: string
  point_unit: string
  point_description: string | null
}

export interface SensorModelInfo {
  model_id: string
  sensor_type: string
  model_name: string
  remark: string
  points: ModelPointItem[]
}

export interface SensorModelDetail {
  model_id: string
  sensor_type: string
  model_name: string
  remark: string
  points: ModelPointItem[]
}

// ==================== 分页查询 ====================

export async function fetchSensorModelPage(
  page: number,
  limit: number,
): Promise<{ data: SensorModelInfo[]; total: number }> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/models/list?page=${page}&limit=${limit}`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Accept': 'application/json',
    },
  })

  if (!response.ok) {
    throw new Error(await extractMessage(response))
  }

  const result = await response.json()

  if (!result.success || result.code !== 200) {
    throw new Error(result.message || '获取型号列表失败')
  }

  return { data: result.data.items, total: result.data.total }
}

// ==================== 查询详情 ====================

export async function fetchSensorModelDetail(modelId: string): Promise<SensorModelDetail> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/models/find/${modelId}`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Accept': 'application/json',
    },
  })

  if (!response.ok) {
    throw new Error(await extractMessage(response))
  }

  const result = (await response.json()) as ApiResponse<SensorModelDetail>

  if (!result.success || result.code !== 200) {
    throw new Error(result.message || '获取型号详情失败')
  }

  return result.data
}

// ==================== 新增 ====================

export interface CreateSensorModelPayload {
  sensor_type?: string | null
  model_name?: string | null
  remark?: string | null
  points?: { point_id: string }[]
}

export async function createSensorModel(payload: CreateSensorModelPayload): Promise<SensorModelDetail> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/models/add`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    throw new Error(await extractMessage(response))
  }

  const result = (await response.json()) as ApiResponse<SensorModelDetail>

  if (!result.success || result.code !== 200) {
    throw new Error(result.message || '新增型号失败')
  }

  return result.data
}

// ==================== 修改 ====================

export interface EditSensorModelPayload {
  sensor_type?: string | null
  model_name?: string | null
  remark?: string | null
}

export async function editSensorModel(modelId: string, payload: EditSensorModelPayload): Promise<SensorModelDetail> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/models/edit/${modelId}`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    throw new Error(await extractMessage(response))
  }

  const result = (await response.json()) as ApiResponse<SensorModelDetail>

  if (!result.success || result.code !== 200) {
    throw new Error(result.message || '修改型号失败')
  }

  return result.data
}

// ==================== 删除 ====================

export async function deleteSensorModel(modelId: string): Promise<void> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/models/drop/${modelId}`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Accept': 'application/json',
    },
  })

  if (!response.ok) {
    throw new Error(await extractMessage(response))
  }

  const result = await response.json()

  if (!result.success || result.code !== 200) {
    throw new Error(result.message || '删除型号失败')
  }

  if (result.data && result.data.ok === false) {
    throw new Error(result.message || '删除型号失败')
  }
}
