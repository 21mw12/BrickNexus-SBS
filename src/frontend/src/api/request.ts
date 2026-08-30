import { BASE_URL } from '../config'
import { getToken } from './auth'

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

export interface RequestInfo {
  request_id: string
  name: string
  request_type: string       // "mqtt" | "api"
  request_info: string       // 请求配置（摘要字符串）
  is_active: boolean
}

export interface CreateRequestPayload {
  name: string
  request_type: string       // "mqtt" | "api"
  request_info?: Record<string, any>
}

// ==================== 查询所有请求 ====================

export async function fetchRequestPage(
  page: number,
  limit: number,
  query?: { request_type?: string; keyword?: string },
): Promise<{ data: RequestInfo[]; total: number }> {
  const token = getToken()

  const params = new URLSearchParams({ page: String(page), limit: String(limit) })
  if (query?.request_type) params.set('request_type', query.request_type)
  if (query?.keyword) params.set('keyword', query.keyword)

  const response = await fetch(`${BASE_URL}/request/list?${params}`, {
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
    throw new Error(result.message || '获取请求列表失败')
  }

  return { data: result.data.items, total: result.data.total }
}

// ==================== 查询单个请求 ====================

export interface RequestDetail {
  request_id: string
  name: string
  request_type: string
  request_info: Record<string, any>
  is_active: boolean
}

export async function fetchRequestDetail(requestId: string): Promise<RequestDetail> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/request/find/${requestId}`, {
    method: 'GET',
    headers: { 'Authorization': `Bearer ${token}`, 'Accept': 'application/json' },
  })

  if (!response.ok) throw new Error(await extractMessage(response))

  const result = await response.json()
  if (!result.success || result.code !== 200) throw new Error(result.message || '获取请求详情失败')
  return result.data
}

// ==================== 编辑请求 ====================

export interface EditRequestPayload {
  name?: string
  request_type?: string
  request_info?: Record<string, any>
  time_json_path?: string
  time_parse?: string
}

export async function editRequest(requestId: string, payload: EditRequestPayload): Promise<RequestDetail> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/request/edit/${requestId}`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) throw new Error(await extractMessage(response))

  const result = await response.json()
  if (!result.success || result.code !== 200) throw new Error(result.message || '编辑请求失败')
  return result.data
}

// ==================== 切换启停 ====================

export async function toggleRequest(requestId: string): Promise<void> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/request/toggle/${requestId}`, {
    method: 'POST',
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
    throw new Error(result.message || '切换启停失败')
  }
}

// ==================== 删除请求 ====================

export async function deleteRequest(requestId: string): Promise<void> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/request/drop/${requestId}`, {
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
    throw new Error(result.message || '删除请求失败')
  }

  if (result.data && result.data.ok === false) {
    throw new Error(result.message || '删除请求失败')
  }
}

// ==================== 终端测点树 ====================

export interface PointInfo {
  point_id: string
  point_name: string
  point_unit: string
  json_path: string
}

export interface SensorNode {
  sensor_id: string
  sensor_name: string
  points: PointInfo[]
}

export interface TerminalTree {
  terminal_id: string
  terminal_name: string
  request_id: string | null
  last_receive_time: string | null
  time_json_path: string | null
  time_parse: string | null
  sensors: SensorNode[]
}

export interface EditTerminalPayload {
  request_id?: string
  points?: PointEdit[]
}

export async function fetchTerminalTree(terminalId: string): Promise<TerminalTree> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/terminal_request/tree/${terminalId}`, {
    method: 'GET',
    headers: { 'Authorization': `Bearer ${token}`, 'Accept': 'application/json' },
  })

  if (!response.ok) throw new Error(await extractMessage(response))

  const result = await response.json()
  if (!result.success || result.code !== 200) throw new Error(result.message || '获取终端测点树失败')
  return result.data
}

// ==================== 编辑终端测点树 ====================

export interface PointEdit {
  point_id?: string
  json_path?: string
}

export async function editTerminalTree(terminalId: string, payload: EditTerminalPayload): Promise<TerminalTree> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/terminal_request/edit/${terminalId}`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) throw new Error(await extractMessage(response))

  const result = await response.json()
  if (!result.success || result.code !== 200) throw new Error(result.message || '编辑终端测点失败')
  return result.data
}

// ==================== 测试请求 ====================

export interface TestRequestResult {
  ok: boolean
  data: any
  message: string
}

export async function testRequest(requestId: string, timeout?: number): Promise<TestRequestResult> {
  const token = getToken()

  const body: Record<string, any> = {}
  if (timeout != null) body.timeout = timeout

  const response = await fetch(`${BASE_URL}/request/test/${requestId}`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify(body),
  })

  if (!response.ok) throw new Error(await extractMessage(response))

  const result = await response.json()
  if (!result.success || result.code !== 200) throw new Error(result.message || '测试请求失败')
  return result.data
}

// ==================== 新增请求 ====================

export async function createRequest(payload: CreateRequestPayload): Promise<any> {
  const token = getToken()

  const response = await fetch(`${BASE_URL}/request/add`, {
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

  const result = await response.json()

  if (!result.success || result.code !== 200) {
    throw new Error(result.message || '新增请求失败')
  }

  return result.data
}

// ==================== Request V2（独立通道配置） ====================
export type RequestProtocol = 'mqtt' | 'http'
export interface RequestListItemV2 { request_id: string; name: string; type: RequestProtocol; status: boolean; created_at: string }
export interface RequestDetailV2 extends RequestListItemV2 { channel_id: string; interval_seconds: number; time_json_path: string | null; time_format: string | null; mqtt_topic: string | null; http_method: 'GET'|'POST'|null; http_path: string|null; http_header: Record<string,unknown>|null; http_params: Record<string,unknown>|null; http_body: Record<string,unknown>|null; channel: Record<string,unknown> }
export interface RequestPayloadV2 { name:string;type:RequestProtocol;channel_id:string;interval_seconds:number;time_json_path:string|null;time_format:string|null;mqtt_topic?:string;http_method?:'GET'|'POST';http_path?:string;http_header?:Record<string,unknown>|null;http_params?:Record<string,unknown>|null;http_body?:Record<string,unknown>|null }
export interface RequestQueryV2 { name?:string;type?:RequestProtocol;status?:boolean;channel_id?:string }
async function requestV2<T>(path:string,method='GET',body?:unknown):Promise<T>{const response=await fetch(`${BASE_URL}${path}`,{method,headers:{Authorization:`Bearer ${getToken()}`,Accept:'application/json',...(body!==undefined?{'Content-Type':'application/json'}:{})},body:body===undefined?undefined:JSON.stringify(body)});if(!response.ok)throw new Error(await extractMessage(response));const result=await response.json();if(!result.success||result.code!==200)throw new Error(result.message||'请求失败');return result.data}
export async function fetchRequestPageV2(page:number,limit:number,query:RequestQueryV2={}){const data=await requestV2<{total:number;items:RequestListItemV2[]}>(`/request/list?page=${page}&limit=${limit}`,'POST',query);return{data:data.items,total:data.total}}
export const fetchRequestDetailV2=(id:string)=>requestV2<RequestDetailV2>(`/request/find/${encodeURIComponent(id)}`)
export const createRequestV2=(payload:RequestPayloadV2)=>requestV2<RequestDetailV2>('/request/add','POST',payload)
export const editRequestV2=(id:string,payload:RequestPayloadV2)=>requestV2<RequestDetailV2>(`/request/edit/${encodeURIComponent(id)}`,'POST',payload)
export const toggleRequestV2=(id:string)=>requestV2<RequestDetailV2>(`/request/toggle/${encodeURIComponent(id)}`,'POST')
export const deleteRequestV2=(id:string)=>requestV2<{ok:boolean}>(`/request/drop/${encodeURIComponent(id)}`)
export const testRequestV2=(id:string,timeout=10)=>requestV2<TestRequestResult>(`/request/test/${encodeURIComponent(id)}`,'POST',{timeout})
export const editRequestTimeV2=(id:string,time_json_path:string|null,time_format:string|null)=>requestV2<RequestDetailV2>(`/request/edit/${encodeURIComponent(id)}`,'POST',{time_json_path,time_format})
