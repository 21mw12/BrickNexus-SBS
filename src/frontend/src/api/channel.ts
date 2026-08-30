import { BASE_URL } from '../config'
import { getToken } from './auth'

export type ChannelType = 'mqtt' | 'http'
export interface MqttChannelListItem { channel_mqtt_id: string; broker_host: string; broker_port: number; created_at: string }
export interface MqttChannelDetail extends MqttChannelListItem { client_id: string; username: string | null; password_configured: boolean; qos: number; connect_timeout: number; data_timeout: number }
export interface HttpChannelListItem { channel_http_id: string; base_url: string; created_at: string }
export interface HttpChannelDetail extends HttpChannelListItem { default_headers: Record<string, string>; default_timeout: number }
export interface MqttChannelPayload { broker_host: string; broker_port: number; username?: string | null; password?: string | null; qos: number; connect_timeout: number; data_timeout: number }
export interface HttpChannelPayload { base_url: string; default_headers?: Record<string, string> | null; default_timeout: number }

interface ApiResponse<T> { success: boolean; code: number; message: string; data: T }
async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, { method, headers: { Authorization: `Bearer ${getToken()}`, Accept: 'application/json', ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}) }, body: body === undefined ? undefined : JSON.stringify(body) })
  if (!response.ok) { let message = `请求失败（${response.status}）`; try { message = (await response.json())?.message || message } catch {} throw new Error(message) }
  const result = await response.json() as ApiResponse<T>
  if (!result.success || result.code !== 200) throw new Error(result.message || '请求失败')
  return result.data
}

export async function fetchMqttChannels(page: number, limit: number, query: { broker_host?: string; username?: string }) { const data = await request<{ total: number; items: MqttChannelListItem[] }>(`/channel/mqtt/list?page=${page}&limit=${limit}`, 'POST', query); return { data: data.items, total: data.total } }
export const fetchMqttChannel = (id: string) => request<MqttChannelDetail>(`/channel/mqtt/find/${encodeURIComponent(id)}`)
export const createMqttChannel = (payload: MqttChannelPayload) => request<MqttChannelDetail>('/channel/mqtt/add', 'POST', payload)
export const editMqttChannel = (id: string, payload: Partial<MqttChannelPayload>) => request<MqttChannelDetail>(`/channel/mqtt/edit/${encodeURIComponent(id)}`, 'POST', payload)
export const deleteMqttChannel = (id: string) => request<{ ok: boolean }>(`/channel/mqtt/drop/${encodeURIComponent(id)}`)

export async function fetchHttpChannels(page: number, limit: number, query: { base_url?: string }) { const data = await request<{ total: number; items: HttpChannelListItem[] }>(`/channel/http/list?page=${page}&limit=${limit}`, 'POST', query); return { data: data.items, total: data.total } }
export const fetchHttpChannel = (id: string) => request<HttpChannelDetail>(`/channel/http/find/${encodeURIComponent(id)}`)
export const createHttpChannel = (payload: HttpChannelPayload) => request<HttpChannelDetail>('/channel/http/add', 'POST', payload)
export const editHttpChannel = (id: string, payload: Partial<HttpChannelPayload>) => request<HttpChannelDetail>(`/channel/http/edit/${encodeURIComponent(id)}`, 'POST', payload)
export const deleteHttpChannel = (id: string) => request<{ ok: boolean }>(`/channel/http/drop/${encodeURIComponent(id)}`)
