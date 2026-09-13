import { BASE_URL } from '../config'
import { getToken } from './auth'
import type { RuleConfig } from './rule'

export interface GeneratorConfig { noise: number; min: number; max: number }
export interface SandboxPoint { id: string; source_point_id?: string | null; name: string; unit: string; base_value: number; generator: GeneratorConfig }
export interface SandboxSensor { name: string; model_id?: string | null; points: SandboxPoint[] }
export interface SandboxTerminal { name: string; sensors: SandboxSensor[]; /** legacy import only */ interval_ticks?: number }
export interface SandboxRuleRef { rule_id: string; state: boolean; effective_tick: number }
export interface SandboxConfig { speed: 1 | 2 | 5 | 10; terminals: SandboxTerminal[]; sandbox_rule: SandboxRuleRef[] }
export interface Sandbox { sandbox_id: string; sandbox_name: string; description: string | null; state: boolean; tick: number; created_at: string; config: SandboxConfig }
export interface SandboxEvent { event_id: string; sandbox_id: string; tick: number; event_type: string; payload: Record<string, any> }
export interface ActiveFault { event_id: string; fault_type: string; point_id: string; start_tick: number; end_tick: number | null; parameters: Record<string, number | string> }
export interface SandboxRule { rule_id: string; state: boolean; effective_tick: number; rule_name: string; description?: string; point_id?: string; error?: string; config?: RuleConfig }
export interface SandboxModelPoint { point_id: string; point_name: string; point_unit: string; point_description?: string | null }
export interface SandboxSensorModel { model_id: string; model_name: string; sensor_type?: string | null; remark?: string | null; points: SandboxModelPoint[] }
export interface SandboxBaselineSource { sensor_id: string; sensor_name: string; model_id: string; path: string }
export interface SandboxBaselinePoint { source_point_id: string; source_definition_id: string; id: string; name: string; unit: string; base_value: number; generator: GeneratorConfig; sample_count: number; available: boolean }
export interface SandboxBaseline { sensor_id: string; sensor_name: string; model_id: string; start_time: string; end_time: string; points: SandboxBaselinePoint[] }
export interface SandboxSchedule { server_time: string; next_tick_at: string | null; tick_interval_seconds: number }

async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, { method, headers: { Authorization: `Bearer ${getToken()}`, Accept: 'application/json', ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) }, body: body === undefined ? undefined : JSON.stringify(body) })
  const result = await response.json().catch(() => null)
  if (!response.ok || !result?.success) throw new Error(result?.message || `请求失败（${response.status}）`)
  return result.data
}

export async function listSandboxes(page = 1, limit = 100) { return request<{ total: number; items: Sandbox[] }>(`/sandbox/list?page=${page}&limit=${limit}`) }
export const findSandbox = (id: string) => request<Sandbox>(`/sandbox/find/${encodeURIComponent(id)}`)
export const createSandbox = (data: { sandbox_name: string; description?: string | null; config: SandboxConfig }) => request<Sandbox>('/sandbox/add', 'POST', data)
export const editSandbox = (id: string, data: { sandbox_name: string; description?: string | null; config: SandboxConfig }) => request<Sandbox>(`/sandbox/edit/${encodeURIComponent(id)}`, 'POST', data)
export const toggleSandbox = (id: string) => request<{ sandbox_id: string; state: boolean; tick: number } & SandboxSchedule>(`/sandbox/toggle/${encodeURIComponent(id)}`, 'POST')
export const pauseSandbox = (id: string) => request<{ sandbox_id: string; state: false; tick: number } & SandboxSchedule>(`/sandbox/pause/${encodeURIComponent(id)}`, 'POST')
export const setSandboxSpeed = (id: string, speed: 1 | 2 | 5 | 10) => request<{ sandbox_id: string; speed: 1 | 2 | 5 | 10; tick: number } & SandboxSchedule>(`/sandbox/speed/${encodeURIComponent(id)}`, 'POST', { speed })
export const deleteSandbox = (id: string) => request(`/sandbox/drop/${encodeURIComponent(id)}`)
export const fetchSandboxModels = () => request<SandboxSensorModel[]>('/sandbox/catalog/models')
export const fetchSandboxModelSensors = (modelId: string) => request<SandboxBaselineSource[]>(`/sandbox/catalog/models/${encodeURIComponent(modelId)}/sensors`)
export const fetchBaseline = (sensorId: string) => request<SandboxBaseline>(`/sandbox/baseline/${encodeURIComponent(sensorId)}`)
export const querySandboxData = (id: string, body: { point_ids: string[]; start_tick: number; end_tick: number; method: 'lttb'; sample_count: number }) => request<any>(`/sandbox/${encodeURIComponent(id)}/measurements/query`, 'POST', body)
export const injectFault = (id: string, body: any) => request<SandboxEvent>(`/sandbox/${encodeURIComponent(id)}/faults/inject`, 'POST', body)
export const stopFault = (id: string, eventId: string) => request<SandboxEvent>(`/sandbox/${encodeURIComponent(id)}/faults/${encodeURIComponent(eventId)}/stop`, 'POST')
export const listActiveFaults = (id: string) => request<ActiveFault[]>(`/sandbox/${encodeURIComponent(id)}/faults/active`)
export const listSandboxEvents = (id: string, page = 1, limit = 50) => request<{ total: number; items: SandboxEvent[] }>(`/sandbox/${encodeURIComponent(id)}/events?page=${page}&limit=${limit}`, 'POST', {})
export const listSandboxRules = (id: string) => request<SandboxRule[]>(`/sandbox/${encodeURIComponent(id)}/rules/list`)
export const findSandboxRule = (id: string, ruleId: string) => request<SandboxRule>(`/sandbox/${encodeURIComponent(id)}/rules/find/${encodeURIComponent(ruleId)}`)
export const createSandboxRule = (id: string, rule: RuleConfig) => request<SandboxRule>(`/sandbox/${encodeURIComponent(id)}/rules/add`, 'POST', rule)
export const editSandboxRule = (id: string, ruleId: string, rule: RuleConfig) => request<SandboxRule>(`/sandbox/${encodeURIComponent(id)}/rules/edit/${encodeURIComponent(ruleId)}`, 'POST', rule)
export const toggleSandboxRule = (id: string, ruleId: string) => request<SandboxRule>(`/sandbox/${encodeURIComponent(id)}/rules/toggle/${encodeURIComponent(ruleId)}`, 'POST')
export const deleteSandboxRule = (id: string, ruleId: string) => request(`/sandbox/${encodeURIComponent(id)}/rules/drop/${encodeURIComponent(ruleId)}`)

export async function importSandbox(file: File, name: string, description: string) {
  const form = new FormData(); form.append('file', file); form.append('sandbox_name', name); if (description) form.append('description', description)
  const response = await fetch(`${BASE_URL}/sandbox/import`, { method: 'POST', headers: { Authorization: `Bearer ${getToken()}` }, body: form })
  const result = await response.json().catch(() => null)
  if (!response.ok || !result?.success) throw new Error(result?.message || '导入失败')
  return result.data as Sandbox
}

async function download(path: string, filename: string) {
  const response = await fetch(`${BASE_URL}${path}`, { headers: { Authorization: `Bearer ${getToken()}` } })
  if (!response.ok) throw new Error('下载失败')
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export const downloadSandbox = (id: string) => download(`/sandbox/export/${encodeURIComponent(id)}`, `sandbox-${id}.json`)
export const downloadMeasurements = (id: string) => download(`/sandbox/${encodeURIComponent(id)}/measurements/export`, `sandbox-${id}-measurements.csv`)

/** Best-effort pause for pagehide/unload, where awaiting a normal request is unsafe. */
export function pauseSandboxOnLeave(id: string) {
  const token = getToken()
  if (!token) return
  void fetch(`${BASE_URL}/sandbox/pause/${encodeURIComponent(id)}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
    keepalive: true,
  }).catch(() => undefined)
}
