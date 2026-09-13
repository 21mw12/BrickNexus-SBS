import { BASE_URL } from '../config'
import { getToken } from './auth'

export type InterpretationConfidence = 'high' | 'medium' | 'low'

export interface InterpretationItem {
  title: string
  statement: string
  evidence: string[]
  confidence: InterpretationConfidence
}

export interface AnalysisInterpretation {
  overview: string
  findings: InterpretationItem[]
  inferences: InterpretationItem[]
  cautions: string[]
  recommended_checks: string[]
  limitations: string[]
}

interface AgentResponseBase {
  conversation_id: string
  conversation_reset: boolean
}

export interface AnalysisAgentReportResponse extends AgentResponseBase {
  response_type: 'report'
  report: AnalysisInterpretation
  reply: null
}

export interface AnalysisAgentAnswerResponse extends AgentResponseBase {
  response_type: 'answer'
  report: null
  reply: string
}

export type AnalysisAgentResponse = AnalysisAgentReportResponse | AnalysisAgentAnswerResponse

interface ApiResponse<T> { success: boolean; code: number; message: string; data: T | null }

export async function respondToAnalysis(
  analysisId: string,
  signal: AbortSignal,
  conversationId?: string,
  message?: string,
): Promise<AnalysisAgentResponse> {
  const response = await fetch(`${BASE_URL}/agent/analysis/respond`, {
    method: 'POST',
    signal,
    headers: {
      Authorization: `Bearer ${getToken()}`,
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      analysis_id: analysisId,
      conversation_id: conversationId || null,
      message: message || null,
    }),
  })
  const body = await response.json().catch(() => null) as ApiResponse<AnalysisAgentResponse> | null
  if (!response.ok || !body?.success || !body.data) throw new Error(body?.message || `AI分析请求失败（${response.status}）`)
  return body.data
}
