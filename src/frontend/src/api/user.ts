import { BASE_URL } from '../config'
import { getToken, type ApiResponse } from './auth'

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

export interface RoleInfo {
  role_id: string
  name: string
  describe: string
}

export interface AccountInfo {
  user_id: string
  account: string
  nickname: string
  role_name: string
}

// ==================== 角色 ====================

export interface RoleQuery {
  name?: string
  describe?: string
}

interface RoleListResponse {
  success: boolean
  code: number
  message: string
  data: {
    items: RoleInfo[]
    total: number
  }
}

/**
 * 角色分页查询
 */
export async function fetchRolePage(
  page: number,
  limit: number,
  query: RoleQuery = {},
): Promise<{ data: RoleInfo[]; total: number }> {
  const token = getToken()

  const body: Record<string, string> = {}
  if (query.name) body.name = query.name
  if (query.describe) body.describe = query.describe

  const response = await fetch(`${BASE_URL}/user/role/form?page=${page}&limit=${limit}`, {
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

  const result = (await response.json()) as RoleListResponse

  if (!result.success || result.code !== 200) {
    throw new Error(result.message || '获取角色列表失败')
  }

  return { data: result.data.items, total: result.data.total }
}

/**
 * 一次性拉取全部角色（供下拉框等场景使用）
 */
export async function fetchRoles(): Promise<RoleInfo[]> {
  const result = await fetchRolePage(1, 99)
  return result.data
}

// ==================== 账号 ====================

export interface AccountQuery {
  account?: string
  role_id?: string
}

interface AccountListResponse {
  items?: AccountInfo[]
  total?: number
  data?: {
    items?: AccountInfo[]
    total?: number
  }
  success?: boolean
  code?: number
  message?: string
}

/**
 * 账号分页查询
 */
export async function fetchAccounts(
  page: number,
  limit: number,
  query: AccountQuery = {},
): Promise<{ data: AccountInfo[]; total: number }> {
  const token = getToken()

  const body: Record<string, string> = {}
  if (query.account) body.account = query.account
  if (query.role_id) body.role_id = query.role_id

  const response = await fetch(`${BASE_URL}/user/account/form?page=${page}&limit=${limit}`, {
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

  const result = (await response.json()) as AccountListResponse

  // 检查业务错误
  if (result.success === false || (result.code && result.code !== 200)) {
    throw new Error(result.message || '获取账号列表失败')
  }

  // 兼容两种格式：{ items, total } 或 { success, data: { items, total } }
  if (result.items) {
    return { data: result.items, total: result.total ?? result.items.length }
  }
  if (result.data?.items) {
    return { data: result.data.items, total: result.data.total ?? result.data.items.length }
  }

  return { data: [], total: 0 }
}

// ==================== 新增账号 ====================

export interface CreateAccountPayload {
  account: string
  password: string
  nickname: string
  role_id: string
}

export interface CreateAccountResult {
  user_id: string
  role_id: string
  account: string
  nickname: string
}

/**
 * 新增账号
 */
export async function createAccount(payload: CreateAccountPayload): Promise<CreateAccountResult> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/user/account/add`, {
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

  const result = (await response.json()) as ApiResponse<CreateAccountResult>

  if (!result.success || result.code !== 200) {
    throw new Error(result.message || '创建账号失败')
  }

  return result.data
}

// ==================== 账号资产权限项 ====================

export interface AssetPermItem {
  asset_id: string
  perm_retrieve: boolean  // R 查看
  perm_update: boolean    // U 修改
  perm_delete: boolean    // D 删除
  perm_operate: boolean   // O 操作（仅终端和传感器）
}

// ==================== 查询账号详情 ====================

export interface AccountDetail {
  user_id: string
  account: string
  nickname: string
  role_id: string
  role_name: string
  asset_permissions: AssetPermItem[]
}

/**
 * 查询账号详情（含用户级资产权限）
 */
export async function fetchAccountDetail(userId: string): Promise<AccountDetail> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/user/account/find/${userId}`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Accept': 'application/json',
    },
  })

  if (!response.ok) {
    throw new Error(await extractMessage(response))
  }

  const result = (await response.json()) as ApiResponse<AccountDetail>

  if (!result.success || result.code !== 200) {
    throw new Error(result.message || '获取账号详情失败')
  }

  return result.data
}

// ==================== 编辑账号 ====================

export interface EditAccountPayload extends CreateAccountPayload {
  asset_permissions?: AssetPermItem[]
}

/**
 * 编辑账号
 */
export async function editAccount(userId: string, payload: EditAccountPayload): Promise<CreateAccountResult> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/user/account/edit/${userId}`, {
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

  const result = (await response.json()) as ApiResponse<CreateAccountResult>

  if (!result.success || result.code !== 200) {
    throw new Error(result.message || '编辑账号失败')
  }

  return result.data
}

// ==================== 删除账号 ====================

/**
 * 删除账号
 */
export async function deleteAccount(userId: string): Promise<void> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/user/account/drop/${userId}`, {
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
    throw new Error(result.message || '删除账号失败')
  }

  // 检查 data.ok
  if (result.data && result.data.ok === false) {
    throw new Error(result.message || '删除账号失败')
  }
}

// ==================== 重置密码 ====================

/**
 * 重置账号密码
 */
export async function resetPassword(userId: string): Promise<void> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/user/account/resetPwd/${userId}`, {
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
    throw new Error(result.message || '重置密码失败')
  }
}

// ==================== 个人页面 ====================

export interface PermissionTreeNode {
  asset_id: string
  name: string
  permission: string  // "R", "RU", "RUD" 等组合字符串，无权限则为空串
  sub_assets?: PermissionTreeNode[]
}

export interface MyProfile {
  user_id: string
  account: string
  nickname: string
  role_name: string
  create_types: string[]
  asset_tree: PermissionTreeNode[]
}

/**
 * 获取当前登录用户的个人页面数据
 * GET /user/account/me
 */
export async function fetchMyProfile(): Promise<MyProfile> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/user/account/me`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Accept': 'application/json',
    },
  })

  if (!response.ok) {
    throw new Error(await extractMessage(response))
  }

  const result = (await response.json()) as ApiResponse<MyProfile>

  if (!result.success || result.code !== 200) {
    throw new Error(result.message || '获取个人信息失败')
  }

  return result.data
}

// ==================== 页面树 ====================

export interface PageTreeNode {
  page_id: string
  page_id_parent: string | null
  name: string
  path_code: string
  sub_pages?: PageTreeNode[]
}

/**
 * 获取所有页面（树结构）
 */
export async function fetchPageTree(): Promise<PageTreeNode[]> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/user/page/tree`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Accept': 'application/json',
    },
  })

  if (!response.ok) {
    throw new Error(await extractMessage(response))
  }

  const result = (await response.json()) as ApiResponse<PageTreeNode[]>

  if (!result.success || result.code !== 200) {
    throw new Error(result.message || '获取页面树失败')
  }

  return result.data
}

// ==================== 角色详情 ====================

export interface AssetTypePermission {
  type: string
  permission: string  // "C", "D", "CD"
}

export interface AssetIdPermissionNode {
  asset_id: string
  name?: string  // 仅查询响应（树形）返回；请求时平铺发送无需此字段
  permission: string  // "R", "U", "D", "O", "RU", "RUD", "RO" 等
  sub_assets?: AssetIdPermissionNode[]  // 查询响应中包含子节点，请求时平铺发送无需此字段
}

export interface AssetPermission {
  part_asset_type?: AssetTypePermission[]
  part_asset_id?: AssetIdPermissionNode[]
}

export interface RoleDetail {
  role_id: string
  name: string
  describe: string
  page_ids: string[]
  asset_permission?: AssetPermission
}

/**
 * 根据 ID 获取角色详细信息
 */
export async function fetchRoleDetail(roleId: string): Promise<RoleDetail> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/user/role/find/${roleId}`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Accept': 'application/json',
    },
  })

  if (!response.ok) {
    throw new Error(await extractMessage(response))
  }

  const result = (await response.json()) as ApiResponse<RoleDetail>

  if (!result.success || result.code !== 200) {
    throw new Error(result.message || '获取角色详情失败')
  }

  return result.data
}

// ==================== 创建角色 ====================

export interface CreateRolePayload {
  name: string
  describe?: string
  page_ids?: string[]
  asset_permission?: AssetPermission
}

export interface CreateRoleResult {
  role_id: string
  name: string
  describe: string
}

/**
 * 新增角色
 */
export async function createRole(payload: CreateRolePayload): Promise<CreateRoleResult> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/user/role/add`, {
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

  const result = (await response.json()) as ApiResponse<CreateRoleResult>

  if (!result.success || result.code !== 200) {
    throw new Error(result.message || '创建角色失败')
  }

  return result.data
}

// ==================== 编辑角色 ====================

export type EditRolePayload = CreateRolePayload

/**
 * 修改角色
 */
export async function editRole(roleId: string, payload: EditRolePayload): Promise<CreateRoleResult> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/user/role/edit/${roleId}`, {
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

  const result = (await response.json()) as ApiResponse<CreateRoleResult>

  if (!result.success || result.code !== 200) {
    throw new Error(result.message || '修改角色失败')
  }

  return result.data
}

// ==================== 删除角色 ====================

/**
 * 删除角色
 */
export async function deleteRole(roleId: string): Promise<void> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/user/role/drop/${roleId}`, {
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
    throw new Error(result.message || '删除角色失败')
  }

  // 检查 data.ok：API 可能返回 success:true 但 data.ok:false
  if (result.data && result.data.ok === false) {
    throw new Error(result.message || '删除角色失败')
  }
}
