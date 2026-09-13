import { BASE_URL } from '../config'
import { getToken } from './auth'
import type { PointInfo } from './request'

export type AnalysisType = 'anomaly' | 'clustering' | 'forecasting'
export type Aggregation = 'mean' | 'min' | 'max' | 'first' | 'last'
export type MissingStrategy = 'drop' | 'interpolate' | 'forward_fill' | 'reject'

export interface SelectedAnalysisPoint extends PointInfo {
  sensor_name: string
  terminal_name: string
  room_name: string
  path: string
}

export interface AlgorithmParameter { name: string; label?: string; description?: string; type: 'number'|'integer'|'select'|'text'; default: unknown; minimum?: number; maximum?: number; options?: string[]; option_labels?: Record<string,string>; visible_when?: Record<string,string> }
export interface AlgorithmSpec { analysis_type: AnalysisType; name: string; label: string; description?: string; modes: Array<'per_point'|'joint'>; scaling: string; minimum_samples: number; parameters: AlgorithmParameter[] }
export type AlgorithmCatalog = Record<AnalysisType, AlgorithmSpec[]>

export interface AnalyticsRequest {
  analysis_type: AnalysisType
  point_ids: string[]
  start_time: string
  end_time: string
  sample_count: number
  preprocessing: { aggregation: Aggregation; missing_strategy: MissingStrategy; max_gap: number }
  algorithm: { name: string; mode: 'per_point'|'joint'; parameters: Record<string, unknown> }
}

export interface AnalyticsWarning { code: string; level: string; point_id?: string|null; message: string }
export interface AnalyticsAIContext {
  available: boolean
  analysis_id: string | null
  expires_at: string | null
  reason_code: string | null
}
export interface AnalyticsQuality {
  raw_count: number
  bucket_count: number
  valid_count: number
  missing_count: number
  missing_ratio: number
  interpolated_count: number
  dropped_count: number
  constant_point_ids: string[]
  low_variance_point_ids: string[]
  max_consecutive_gap: number
}

export interface AnomalyEvent {
  start_time: string
  end_time: string
  point_ids: string[]
  sample_count: number
  max_score: number
}

export interface AnomalySeriesResult {
  point_ids: string[]
  times: string[]
  values_by_point: Array<Array<number | null>>
  labels: boolean[]
  raw_scores: Array<number | null>
  risk_scores: Array<number | null>
  threshold: number
  events: AnomalyEvent[]
}

export interface AnomalyAnalysisResult { series: AnomalySeriesResult[] }

export interface ClusterFeatureHighlight { point_id: string; direction: 'high'|'low'; strength: number }
export interface ClusterFeatureSummary { cluster: number; highlights: ClusterFeatureHighlight[] }
export interface ClusterCandidateScore { cluster_count: number; silhouette_score: number; inertia: number }
export interface ClusteringAnalysisResult {
  cluster_count: number
  labels: number[]
  centers: number[][]
  silhouette_score: number
  inertia: number
  candidate_scores: ClusterCandidateScore[]
  pca: { coordinates: number[][]; explained_variance_ratio: number[]; total_explained_variance: number }
  feature_summaries: ClusterFeatureSummary[]
  point_ids: string[]
  times: string[]
  cluster_sizes: number[]
  summaries: string[]
}

export interface ForecastMetrics { mae: number; rmse: number; smape: number }
export interface ForecastPointSuccess {
  point_id: string
  status: 'success'
  history_times: string[]
  history_values: Array<number | null>
  backtest_times: string[]
  backtest_values: number[]
  forecast_times: string[]
  forecast_values: number[]
  lower: number[] | null
  upper: number[] | null
  metrics: ForecastMetrics
}
export interface ForecastPointFailure { point_id: string; status: 'failed'; message: string }
export type ForecastPointResult = ForecastPointSuccess | ForecastPointFailure
export interface ForecastingAnalysisResult { points: ForecastPointResult[]; horizon: number }

interface AnalyticsResultBase {
  algorithm: string
  mode: string
  timezone: string
  range: { start_time: string; requested_end_time: string; actual_end_time: string; was_clipped: boolean }
  sampling: { requested_sample_count: number; actual_sample_count: number; interval_seconds: number; aggregation: string }
  preprocessing: Record<string, unknown>
  parameters: Record<string, unknown>
  quality: AnalyticsQuality
  warnings: AnalyticsWarning[]
  ai_context?: AnalyticsAIContext
}

export interface AnomalyAnalyticsResult extends AnalyticsResultBase { analysis_type: 'anomaly'; result: AnomalyAnalysisResult }
export interface ClusteringAnalyticsResult extends AnalyticsResultBase { analysis_type: 'clustering'; result: ClusteringAnalysisResult }
export interface ForecastingAnalyticsResult extends AnalyticsResultBase { analysis_type: 'forecasting'; result: ForecastingAnalysisResult }
export type AnalyticsResult = AnomalyAnalyticsResult | ClusteringAnalyticsResult | ForecastingAnalyticsResult

interface ApiResponse<T> { success: boolean; code: number; message: string; data: T }

async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, { method, headers: { Authorization: `Bearer ${getToken()}`, Accept: 'application/json', ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) }, body: body === undefined ? undefined : JSON.stringify(body) })
  const result = await response.json().catch(() => null) as ApiResponse<T> | null
  if (!response.ok || !result?.success) throw new Error(result?.message || `请求失败（${response.status}）`)
  return result.data
}

export const fetchAnalyticsAlgorithms = () => request<AlgorithmCatalog>('/analytics/algorithms')
export const runAnalytics = (payload: AnalyticsRequest) => request<AnalyticsResult>('/analytics/run', 'POST', payload)
