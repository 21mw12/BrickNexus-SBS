import { BASE_URL } from '../config'
import { getToken } from './auth'

export type LLMServiceType = 'vllm' | 'ollama' | 'deepseek'

export interface OpenAICompatibleContent {
  base_url: string
  model_name: string
  model_type: 'chat'
  max_tokens: number
  api_key?: string
  api_key_configured?: boolean
}

export interface OllamaContent {
  base_url: string
  model_name: string
  model_type: 'chat'
  num_ctx: number
}

export type LLMContent = OpenAICompatibleContent | OllamaContent

export interface LLMConfigItem {
  llm_id: string
  service_name: string
  service_type: LLMServiceType
  content: LLMContent
  is_use: boolean
  created_at: string
}

export interface LLMConfigPayload {
  service_name: string
  service_type: LLMServiceType
  content: Record<string, unknown>
}

export interface LLMTestPayload {
  service_type: LLMServiceType
  content: Record<string, unknown>
}

export interface LLMTestResult {
  connected: boolean
  latency_ms: number
  service_type: LLMServiceType
  model_name: string
  message: string
  error_code?: string
}

interface ApiResponse<T> { success: boolean; code: number; message: string; data: T }

async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${getToken()}`,
      Accept: 'application/json',
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  let result: ApiResponse<T> | null = null
  try { result = await response.json() as ApiResponse<T> } catch {}
  if (!response.ok || !result?.success || result.code !== 200) {
    const error = new Error(result?.message || `请求失败（${response.status}）`) as Error & { data?: unknown }
    error.data = result?.data
    throw error
  }
  return result.data
}

export async function fetchLLMConfigs(page: number, limit: number, filters: { service_name?: string; service_type?: LLMServiceType; is_use?: boolean }) {
  return request<{ total: number; items: LLMConfigItem[] }>(`/settings/llm/list?page=${page}&limit=${limit}`, 'POST', filters)
}

export const fetchLLMConfig = (id: string) => request<LLMConfigItem>(`/settings/llm/find/${encodeURIComponent(id)}`)
export const createLLMConfig = (payload: LLMConfigPayload) => request<LLMConfigItem>('/settings/llm/add', 'POST', payload)
export const editLLMConfig = (id: string, payload: LLMConfigPayload) => request<LLMConfigItem>(`/settings/llm/edit/${encodeURIComponent(id)}`, 'POST', payload)
export const deleteLLMConfig = (id: string) => request<{ ok: boolean }>(`/settings/llm/drop/${encodeURIComponent(id)}`)
export const testLLMDraft = (payload: LLMTestPayload) => request<LLMTestResult>('/settings/llm/test', 'POST', payload)
export const testLLMSaved = (id: string, payload?: LLMTestPayload) => request<LLMTestResult>(`/settings/llm/test/${encodeURIComponent(id)}`, 'POST', payload)
export const activateLLMConfig = (id: string) => request<{ config: LLMConfigItem; test: LLMTestResult }>(`/settings/llm/activate/${encodeURIComponent(id)}`, 'POST')
export const deactivateLLMConfig = (id: string) => request<LLMConfigItem>(`/settings/llm/deactivate/${encodeURIComponent(id)}`, 'POST')
