import { BASE_URL } from '../config'
import { getToken } from './auth'

export type RuleStatus = 'paused' | 'running' | 'validating' | 'compile_failed'
export interface RuleListItem { rule_id: string; rule_name: string; status: RuleStatus; error: string | null; created_at: string }
export type RuleActionType = 'LogAction' | 'EmailAction' | 'SensorControlAction'
export interface RuleAction { action_id?: string; type: RuleActionType; params: { level?: string; content?: string; recipients?: string[]; subject?: string; control_id?: string } }
export interface RuleConfig { rule_name: string; description: string; selector: Record<string, unknown>; condition: Record<string, unknown>; trigger_policy: Record<string, unknown>; actions: RuleAction[] }
export interface RuleDetail extends RuleListItem { rule_file_name: string; sensor_id: string | null; config?: RuleConfig }
export interface RuleEvent { event_id: string; rule_id: string; event_type: 'triggered' | 'recovered'; evidence: Record<string, any>; event_time: string }
export interface RuleTask { task_id: string; rule_id: string; action_type: string; is_executed: boolean; status: 'pending' | 'succeeded' | 'failed'; error: string | null; created_at: string; completed_at: string | null }
export interface RuleOptions { comparison_operators: { value: string; label: string; symbol: string }[]; repeat_policies: { value: string; label: string }[]; operand_types: { value: string; label: string }[]; action_types?: { value: RuleActionType; label: string }[] }

async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, { method, headers: { Authorization: `Bearer ${getToken()}`, Accept: 'application/json', ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}) }, body: body === undefined ? undefined : JSON.stringify(body) })
  if (!response.ok) { try { const data = await response.json(); throw new Error(data?.message || `请求失败（${response.status}）`) } catch (e) { if (e instanceof Error) throw e; throw new Error(`请求失败（${response.status}）`) } }
  const result = await response.json()
  if (!result.success || result.code !== 200) throw new Error(result.message || '请求失败')
  return result.data
}

export async function fetchRulePage(page: number, limit: number, query: Record<string, string>) { const data = await request<{ total: number; items: RuleListItem[] }>(`/rules/list?page=${page}&limit=${limit}`, 'POST', query); return { data: data.items, total: data.total } }
export const fetchRuleDetail = (id: string) => request<RuleDetail>(`/rules/find/${encodeURIComponent(id)}`)
export const fetchRuleOptions = () => request<RuleOptions>('/rules/options')
export const createRule = (config: RuleConfig) => request<RuleDetail>('/rules/add', 'POST', config)
export const editRule = (id: string, config: RuleConfig) => request<RuleDetail>(`/rules/edit/${encodeURIComponent(id)}`, 'POST', config)
export const toggleRule = (id: string) => request<RuleDetail>(`/rules/toggle/${encodeURIComponent(id)}`, 'POST')
export const deleteRule = (id: string) => request<{ ok: boolean }>(`/rules/drop/${encodeURIComponent(id)}`)
export async function fetchRuleEvents(page: number, limit: number, query: Record<string, string>) { const data = await request<{ total: number; items: RuleEvent[] }>(`/rules/events?page=${page}&limit=${limit}`, 'POST', query); return { data: data.items, total: data.total } }
export async function fetchRuleTasks(page: number, limit: number, query: Record<string, string>) { const data = await request<{ total: number; items: RuleTask[] }>(`/rules/tasks?page=${page}&limit=${limit}`, 'POST', query); return { data: data.items, total: data.total } }
export const fetchRuleTtl = (id: string) => request<{ rule_id: string; ttl: string }>(`/rules/ttl/${encodeURIComponent(id)}`)
