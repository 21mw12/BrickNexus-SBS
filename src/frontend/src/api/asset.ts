import { BASE_URL } from '../config'
import { getToken } from './auth'

// ==================== 工具 ====================

/**
 * 尝试从 response body 中提取 message 字段，失败则回退到原始文本
 */
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

export interface AssetInfo {
  id: string
  name: string
  type: string  // 'building' | 'room' | 'terminal' | 'sensor'
  floor_count: number
  room_count: number
  terminal_count: number
  sensor_count: number
  is_use: boolean
  is_online?: boolean  // 仅 terminal / sensor 类型有效
}

export interface AssetQuery {
  name?: string
  is_use?: boolean
  is_online?: boolean
  asset_type?: string
  // 楼宇、房间、终端属性
  number?: string
  // 楼宇属性
  address?: string
  level?: string
  // 房间属性
  room_purpose?: string
  max_current?: string
  manager_name?: string
  // 终端属性
  model?: string
  location?: string
  iot_number?: string
  iot_activate_human?: string
  // 传感器属性
  sensor_type?: string
}

interface AssetListResponse {
  success: boolean
  code: number
  message: string
  data: {
    items: AssetInfo[]
    total: number
  }
}

// ==================== 资产分页查询 ====================

/**
 * 资产分页查询（表结构，支持模糊查询）
 * POST /assets/form?page=XXX&limit=XXX
 */
export async function fetchAssetPage(
  page: number,
  limit: number,
  query: AssetQuery = {},
): Promise<{ data: AssetInfo[]; total: number }> {
  const token = getToken()

  // 构造请求体，只包含有值的字段
  const body: Record<string, unknown> = {}
  if (query.name) body.name = query.name
  if (query.is_use !== undefined) body.is_use = query.is_use
  if (query.is_online !== undefined) body.is_online = query.is_online
  if (query.asset_type) body.asset_type = query.asset_type
  if (query.number) body.number = query.number
  if (query.address) body.address = query.address
  if (query.level) body.level = query.level
  if (query.room_purpose) body.room_purpose = query.room_purpose
  if (query.max_current) body.max_current = query.max_current
  if (query.manager_name) body.manager_name = query.manager_name
  if (query.model) body.model = query.model
  if (query.location) body.location = query.location
  if (query.iot_number) body.iot_number = query.iot_number
  if (query.iot_activate_human) body.iot_activate_human = query.iot_activate_human
  if (query.sensor_type) body.sensor_type = query.sensor_type

  const response = await fetch(`${BASE_URL}/assets/form?page=${page}&limit=${limit}`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    throw new Error(await extractMessage(response))
  }

  const result = (await response.json()) as AssetListResponse

  if (!result.success || result.code !== 200) {
    throw new Error(result.message || '获取资产列表失败')
  }

  return { data: result.data.items, total: result.data.total }
}

// ==================== 新增资产 ====================

export interface CreateAssetPayload {
  name: string
  is_use: boolean
  asset_type: string
  asset_id_parent?: string
  number?: string
  address?: string
  level?: string
  room_purpose?: string
  max_current?: string
  manager_name?: string
  model?: string
  location?: string
  iot_number?: string
  iot_activate_human?: string
  model_id?: string   // 传感器型号ID
}

export interface AssetDetail {
  asset_id: string
  asset_id_parent: string | null
  asset_type: string
  name: string
  floor_count: number
  room_count: number
  terminal_count: number
  sensor_count: number
  is_use: boolean
  is_online?: boolean  // 仅 terminal / sensor 类型有效
  number: string | null
  address: string | null
  asset_parent_name?: string
  model_id?: string      // 传感器型号ID
  sensor_type?: string   // 传感器类型名称
  model_name?: string    // 传感器型号名称
  points?: { point_name: string; point_unit: string; point_description?: string | null }[]  // 传感器测点
}

interface CreateAssetResponse {
  success: boolean
  code: number
  message: string
  data: AssetDetail
}

/**
 * 新增资产
 * POST /assets/add
 */
export async function createAsset(payload: CreateAssetPayload): Promise<AssetDetail> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/assets/add`, {
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

  const result = (await response.json()) as CreateAssetResponse

  if (!result.success || result.code !== 200) {
    throw new Error(result.message || '新增资产失败')
  }

  return result.data
}

// ==================== 资产详情 ====================

/**
 * 根据 ID 获取资产详细信息
 * GET /assets/find/{asset_id}
 */
export async function fetchAssetDetail(assetId: string): Promise<AssetDetail> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/assets/find/${assetId}`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Accept': 'application/json',
    },
  })

  if (!response.ok) {
    throw new Error(await extractMessage(response))
  }

  const result = (await response.json()) as CreateAssetResponse

  if (!result.success || result.code !== 200) {
    throw new Error(result.message || '获取资产详情失败')
  }

  return result.data
}

// ==================== 修改资产 ====================

export interface EditAssetPayload {
  name: string
  is_use: boolean
  asset_type: string
  is_use_all?: boolean   // 启用时是否同时启用所有子资产
  asset_id_parent?: string
  number?: string
  address?: string
  level?: string
  room_purpose?: string
  max_current?: string
  manager_name?: string
  model?: string
  location?: string
  iot_number?: string
  iot_activate_human?: string
}

/**
 * 修改资产
 * POST /assets/edit/{asset_id}
 */
export async function editAsset(assetId: string, payload: EditAssetPayload): Promise<AssetDetail> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/assets/edit/${assetId}`, {
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

  const result = (await response.json()) as CreateAssetResponse

  if (!result.success || result.code !== 200) {
    throw new Error(result.message || '修改资产失败')
  }

  return result.data
}

// ==================== 删除资产 ====================

/**
 * 删除资产
 * GET /assets/drop/{asset_id}
 */
export async function deleteAsset(assetId: string): Promise<void> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/assets/drop/${assetId}`, {
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
    throw new Error(result.message || '删除资产失败')
  }

  // 检查 data.ok：API 可能返回 success:true 但 data.ok:false
  if (result.data && result.data.ok === false) {
    throw new Error(result.message || '删除资产失败')
  }
}

// ==================== 导出资产 ====================

/**
 * 导出资产为 Excel
 * GET /assets/excel
 */
export async function exportAssets(): Promise<void> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/assets/excel`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  })

  if (!response.ok) {
    throw new Error(await extractMessage(response))
  }

  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'assets.xlsx'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

// ==================== 资产树 ====================

export interface AssetTreeNode {
  asset_id: string
  name: string
  asset_type?: string
  type?: string
  is_online?: boolean  // 仅 terminal / sensor
  sub_assets?: AssetTreeNode[]
}

interface AssetTreeResponse {
  success: boolean
  code: number
  message: string
  data: AssetTreeNode[]
}

const assetNameCollator = new Intl.Collator('zh-CN', {
  numeric: true,
  sensitivity: 'base',
})

/**
 * 为树形页面生成展示顺序：保留楼宇和传感器原顺序，
 * 楼层、房间、终端按名称自然升序排列（例如 2层 在 10层 前）。
 */
export function sortAssetTreeForDisplay(tree: AssetTreeNode[]): AssetTreeNode[] {
  function visit(nodes: AssetTreeNode[], depth: number): AssetTreeNode[] {
    const result = nodes.map(node => ({
      ...node,
      sub_assets: node.sub_assets ? visit(node.sub_assets, depth + 1) : node.sub_assets,
    }))

    if (depth >= 1 && depth <= 3) {
      result.sort((left, right) => assetNameCollator.compare(left.name || '', right.name || ''))
    }
    return result
  }

  return visit(tree, 0)
}

/**
 * 获取所有资产（树结构）
 * GET /assets/tree
 */
export async function fetchAssetTree(): Promise<AssetTreeNode[]> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/assets/tree`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Accept': 'application/json',
    },
  })

  if (!response.ok) {
    throw new Error(await extractMessage(response))
  }

  const result = (await response.json()) as AssetTreeResponse

  if (!result.success || result.code !== 200) {
    throw new Error(result.message || '获取资产树失败')
  }

  return result.data
}
