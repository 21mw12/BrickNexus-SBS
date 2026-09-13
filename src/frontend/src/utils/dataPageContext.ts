import type { SelectedAnalysisPoint } from '../api/analytics'
import type { TimeRangeValue } from '../components/data/TimeRangeQueryBar.vue'

interface DataPageContext {
  range: TimeRangeValue
  points: SelectedAnalysisPoint[]
}

const STORAGE_KEY = 'bricknexus:data-page-context'

export function storeDataPageContext(range: TimeRangeValue, points: SelectedAnalysisPoint[]) {
  const payload: DataPageContext = {
    range: { ...range },
    points: points.map(point => ({ ...point })),
  }
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
  } catch {
    // 浏览器禁用会话存储时不影响页面本身的查询功能。
  }
}

export function loadDataPageContext(): DataPageContext | null {
  let raw: string | null = null
  try { raw = sessionStorage.getItem(STORAGE_KEY) } catch { return null }
  if (!raw) return null
  try {
    const payload = JSON.parse(raw) as DataPageContext
    if (!payload.range || !Array.isArray(payload.points)) return null
    return { range: payload.range, points: payload.points }
  } catch {
    return null
  }
}
