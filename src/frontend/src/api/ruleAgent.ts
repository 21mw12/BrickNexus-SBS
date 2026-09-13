import { BASE_URL } from '../config'
import { getToken } from './auth'
import type { RuleAction } from './rule'

export type DraftNumber = number | ''
export interface RuleEditorFields {
  rule_name: string; description: string; selector_id: string
  selector_type: 'PointIdSelector' | 'SemanticPointSelector'
  point_id: string; point_definition_id: string; location_id: string
  location_type: '' | 'building' | 'floor' | 'room'
  logic: 'single' | 'AND' | 'OR' | 'NOT'
  trigger_count: DraftNumber; trigger_duration: DraftNumber
  recovery_count: DraftNumber; recovery_duration: DraftNumber
  repeat_policy: 'OncePerIncident' | 'NewMatch' | 'Periodic'
  repeat_interval: DraftNumber; cooldown: DraftNumber; merge_window: DraftNumber
}
export interface ComparisonForm {
  operator: string; leftType: string; constant: DraftNumber
  samples: DraftNumber; duration: DraftNumber; tolerance: DraftNumber
  window: DraftNumber; timeUnit: DraftNumber; rateReference: 'samples' | 'duration'
}
export interface RuleEditorDraft {
  form: RuleEditorFields; sensor_id: string; comparisons: ComparisonForm[]; actions: RuleAction[]
}
export interface RuleAgentResponse {
  conversation_id: string
  conversation_reset: boolean
  reply: string
  form_data: RuleEditorDraft
}

export async function generateRuleDraft(message: string, current_form: RuleEditorDraft, signal: AbortSignal, conversation_id?: string): Promise<RuleAgentResponse> {
  const response = await fetch(`${BASE_URL}/agent/rule/generate`, {
    method: 'POST', signal,
    headers: { Authorization: `Bearer ${getToken()}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversation_id: conversation_id || null, message, current_form }),
  })
  const body = await response.json()
  if (!response.ok || !body.success) throw new Error(body.message || '规则助手请求失败')
  return body.data
}

export async function closeAgentConversation(conversationId: string): Promise<void> {
  const response = await fetch(`${BASE_URL}/agent/conversations/${encodeURIComponent(conversationId)}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${getToken()}` },
  })
  const body = await response.json()
  if (!response.ok || !body.success) throw new Error(body.message || '关闭对话失败')
}
