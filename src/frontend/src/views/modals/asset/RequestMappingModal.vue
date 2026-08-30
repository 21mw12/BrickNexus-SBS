<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import {
  fetchTerminalTree, editTerminalTree, fetchRequestPage, testRequest,
  type TerminalTree, type RequestInfo, type EditTerminalPayload,
} from '../../../api/request.ts'
import JsonTreeViewer from './JsonTreeViewer.vue'

const props = defineProps<{ visible: boolean; terminalId: string; terminalName: string }>()
const emit = defineEmits<{ close: [] }>()

const loading = ref(false)
const saving = ref(false)
const error = ref('')
const tree = ref<TerminalTree | null>(null)
const timeJsonPath = ref('')
const timeParse = ref('')

// ---------- 左侧：请求绑定 + 测试 ----------
const requestList = ref<RequestInfo[]>([])
const selectedRequestId = ref('')
const timeout = ref(10)
const testing = ref(false)
const testResult = ref('')

async function loadRequests() {
  try {
    const result = await fetchRequestPage(1, 200)
    requestList.value = result.data
  } catch { /* ignore */ }
}

async function loadTree() {
  loading.value = true
  try {
    tree.value = await fetchTerminalTree(props.terminalId)
    selectedRequestId.value = tree.value.request_id || ''
    timeJsonPath.value = tree.value.time_json_path || ''
    timeParse.value = tree.value.time_parse || ''
  } catch (e: any) {
    error.value = e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

// 测试请求
async function handleTest() {
  if (!selectedRequestId.value) return
  testing.value = true
  testResult.value = ''
  try {
    const r = await testRequest(selectedRequestId.value, timeout.value)
    testResult.value = JSON.stringify(r.data ?? r, null, 2)
    // 清除之前的提取结果
    extractedResults.value = {}
    timeExtracted.value = ''
    timeExtractOk.value = true
    timeParsed.value = null
    hasNonNumeric.value = false
  } catch (e: any) {
    testResult.value = `测试失败: ${e?.message}`
  } finally {
    testing.value = false
  }
}

// ---------- JSONPath 提取 ----------
const extractedResults = ref<Record<string, { text: string; num: number | null }>>({})
const timeExtracted = ref('')
const timeExtractOk = ref(true)
const timeParsed = ref<{ year: string; month: string; day: string; hour: string; minute: string; second: string } | null>(null)

function parseTimeWithFormat(raw: string, fmt: string) {
  if (!raw || !fmt) return null
  const tokenMap: Record<string, string> = {
    yyyy: '\\d{4}', yy: '\\d{2}', MM: '\\d{2}', dd: '\\d{2}',
    hh: '\\d{2}', HH: '\\d{2}', mm: '\\d{2}', ss: '\\d{2}',
  }
  const sorted = Object.keys(tokenMap).sort((a, b) => b.length - a.length)
  // 单次替换：先转义特殊字符，再一次性替换所有 token，避免 split/join 二次匹配
  let pattern = fmt.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const tokenRe = new RegExp(sorted.join('|'), 'g')
  pattern = pattern.replace(tokenRe, (m) => `(?<${m}>${tokenMap[m]})`)
  const re = new RegExp('^' + pattern + '$')
  const m = raw.match(re)
  if (!m || !m.groups) return null
  const g = m.groups as Record<string, string>
  let year = g.yyyy || ''
  if (!year && g.yy) {
    const yy = parseInt(g.yy)
    year = String(yy >= 70 ? 1900 + yy : 2000 + yy)
  }
  return {
    year: year || '0000',
    month: g.MM || '00',
    day: g.dd || '00',
    hour: g.hh || g.HH || '00',
    minute: g.mm || '00',
    second: g.ss || '00',
  }
}
const extractError = ref('')
const hasNonNumeric = ref(false)

const parsedTestData = computed(() => {
  if (!testResult.value) return null
  try { return JSON.parse(testResult.value) } catch { return null }
})

// JSONPath 解析：$.values[0].key, $.values[?(@.id=='x')].key 等
function resolveJsonPath(data: any, path: string): any {
  if (!path || path === '$') return data
  let p = path.replace(/^\$\.?/, '')
  if (!p) return data

  // 逐段解析：先按 . 分割，再处理每段中的 [...]
  const tokens: string[] = []
  let i = 0, buf = ''
  while (i < p.length) {
    const ch = p[i]
    if (ch === '.') {
      if (buf) { tokens.push(buf); buf = '' }
    } else if (ch === '[') {
      if (buf) { tokens.push(buf); buf = '' }
      // 找到匹配的 ]
      let j = i + 1, depth = 1
      while (j < p.length && depth > 0) {
        if (p[j] === '[') depth++
        else if (p[j] === ']') depth--
        j++
      }
      tokens.push(p.substring(i, j))
      i = j - 1
    } else {
      buf += ch
    }
    i++
  }
  if (buf) tokens.push(buf)

  let current = data
  for (const token of tokens) {
    if (current == null) return undefined

    // 过滤器：[?(@.key=='value')] 或 [?(@.key=="value")]
    const filter = token.match(/^\[\?\(@\.(\w+)\s*==\s*['"](.+?)['"]\)\]$/)
    if (filter) {
      const fkey = filter[1]!, fval = filter[2]!
      if (!Array.isArray(current)) return undefined
      current = current.find((item: any) => item?.[fkey] == fval)
      continue
    }

    // 数组索引或通配符：key[0], key[*]
    const idx = token.match(/^(\w+)\[(\d+|\*)\]$/)
    if (idx) {
      current = current[idx[1]!]
      if (current == null) return undefined
      if (idx[2] === '*') continue
      current = current[parseInt(idx[2]!)]
      continue
    }

    // 纯索引：[0], [*]
    const bareIdx = token.match(/^\[(\d+|\*)\]$/)
    if (bareIdx) {
      if (!Array.isArray(current)) return undefined
      if (bareIdx[1] === '*') return current
      current = current[parseInt(bareIdx[1]!)]
      continue
    }

    // 普通字段名
    current = current[token]
  }
  return current
}

function handleExtract() {
  if (!testResult.value) {
    extractError.value = '请先进行请求测试'
    return
  }
  extractError.value = ''
  hasNonNumeric.value = false
  timeExtracted.value = ''
  timeExtractOk.value = true
  timeParsed.value = null
  const results: Record<string, { text: string; num: number | null }> = {}
  let data: any
  try {
    data = JSON.parse(testResult.value)
  } catch {
    extractError.value = '测试结果不是有效 JSON'
    return
  }

  if (tree.value) {
    for (const s of tree.value.sensors) {
      for (const p of s.points) {
        if (p.json_path) {
          try {
            const val = resolveJsonPath(data, p.json_path)
            if (val !== undefined && val !== null) {
              const num = parseFloat(val)
              if (!isNaN(num)) {
                results[p.point_id] = { text: String(num), num }
              } else {
                const text = typeof val === 'object' ? JSON.stringify(val) : String(val)
                results[p.point_id] = { text, num: null }
                hasNonNumeric.value = true
              }
            } else {
              results[p.point_id] = { text: '(无匹配)', num: null }
              hasNonNumeric.value = true
            }
          } catch {
            results[p.point_id] = { text: '(提取错误)', num: null }
          }
        }
      }
    }
  }
  extractedResults.value = results

  // 提取时间路径
  if (timeJsonPath.value) {
    const val = resolveJsonPath(data, timeJsonPath.value)
    if (typeof val === 'string') {
      timeExtracted.value = val
      // 按格式解析
      if (timeParse.value) {
        const parsed = parseTimeWithFormat(val, timeParse.value)
        if (parsed) {
          timeParsed.value = parsed
        } else {
          timeExtractOk.value = false
          hasNonNumeric.value = true
        }
      }
    } else {
      timeExtracted.value = val !== undefined ? String(val) : '(无匹配)'
      timeExtractOk.value = false
      hasNonNumeric.value = true
    }
  }
}

// 保存
async function handleSave() {
  saving.value = true
  error.value = ''
  try {
    const payload: EditTerminalPayload = {}
    if (selectedRequestId.value) payload.request_id = selectedRequestId.value

    if (tree.value) {
      payload.points = tree.value.sensors.flatMap(s =>
        s.points.map(p => ({ point_id: p.point_id, json_path: p.json_path || undefined })),
      )
    }

    await editTerminalTree(props.terminalId, payload)
    emit('close')
  } catch (e: any) {
    error.value = e?.message || '保存失败'
  } finally {
    saving.value = false
  }
}

// 打开时加载
watch(() => props.visible, async (v) => {
  if (v) {
    error.value = ''
    testResult.value = ''
    await Promise.all([loadRequests(), loadTree()])
  }
})
</script>

<template>
  <div class="modal-overlay" v-if="visible" @click.self="emit('close')">
    <div class="modal-card">
      <div class="modal-header"><h3>请求映射 - {{ terminalName }}</h3></div>

      <div class="modal-body" v-if="loading"><p class="hint">加载中...</p></div>

      <div class="modal-body mapping-body" v-else-if="tree">
        <!-- ====== 左侧：请求绑定 + 测试 ====== -->
        <div class="mapping-left">
          <div class="field">
            <label class="field-label">终端名称</label>
            <div class="readonly-value">{{ terminalName }}</div>
          </div>

          <div class="field">
            <label class="field-label">绑定请求</label>
            <select v-model="selectedRequestId" class="field-select">
              <option value="">不绑定</option>
              <option v-for="r in requestList" :key="r.request_id" :value="r.request_id">
                {{ r.name }} ({{ r.request_type.toUpperCase() }})
              </option>
            </select>
          </div>

          <div class="field" v-if="selectedRequestId">
            <label class="field-label">超时时间（秒）</label>
            <div class="test-row">
              <input v-model.number="timeout" type="number" class="field-input timeout-input" placeholder="10" />
              <button class="btn btn-outline btn-sm" @click="handleTest" :disabled="testing">
                {{ testing ? '测试中...' : '请求测试' }}
              </button>
            </div>
          </div>

          <div class="field" v-if="testResult">
            <label class="field-label">测试结果</label>
            <div class="test-result">
              <JsonTreeViewer v-if="parsedTestData" :data="parsedTestData" :depth="0" />
              <pre v-else>{{ testResult }}</pre>
            </div>
          </div>
        </div>

        <!-- ====== 右侧：传感器测点树 ====== -->
        <div class="mapping-right">
          <div class="section-header">
            <div>
              <label class="field-label">测点 JSON 路径配置</label>
              <p class="section-hint">使用 JsonPath 标准提取</p>
            </div>
            <button class="btn btn-outline btn-sm" @click="handleExtract">提取测试</button>
          </div>
          <p class="extract-err" v-if="extractError">{{ extractError }}</p>
          <div class="modal-error" v-if="hasNonNumeric" style="margin-top:4px">提取结果中存在非数字值或无匹配项，请检查测点路径配置后重新提取。</div>

          <!-- 时间字段路径（只读） -->
          <div class="time-row">
            <label class="field-label">时间字段路径</label>
            <div class="time-input-row">
              <div class="readonly-value flex-1">{{ timeJsonPath || '未配置' }}</div>
              <span class="extract-box" :class="{ 'extract-err-box': !timeExtractOk || (timeExtracted && timeExtracted === '(无匹配)') }">
                {{ timeExtracted || '' }}
              </span>
            </div>
          </div>

          <!-- 时间解析格式（只读） -->
          <div class="time-row">
            <label class="field-label">时间解析格式</label>
            <div class="time-input-row">
              <div class="readonly-value flex-1">{{ timeParse || '未配置' }}</div>
              <span class="time-display" v-if="timeParsed">
                {{ timeParsed.year }}-{{ timeParsed.month }}-{{ timeParsed.day }} {{ timeParsed.hour }}:{{ timeParsed.minute }}:{{ timeParsed.second }}
              </span>
              <span class="extract-box extract-err-box" v-else-if="timeExtracted && timeParse && !timeExtractOk">格式不匹配</span>
            </div>
          </div>

          <div class="sensor-tree">
            <template v-for="s in tree.sensors" :key="s.sensor_id">
              <div class="sensor-node">
                <div class="sensor-name">📡 {{ s.sensor_name }}</div>
                <div class="point-list">
                  <div class="point-row" v-for="p in s.points" :key="p.point_id">
                    <span class="point-name">{{ p.point_name }} <span class="point-unit">({{ p.point_unit }})</span></span>
                    <input v-model="p.json_path" type="text" placeholder="$.data.xxx" class="field-input json-input" />
                    <span class="extract-box" :class="{ 'extract-err-box': extractedResults[p.point_id]?.num === null }">
                      {{ extractedResults[p.point_id]?.text || '' }}
                    </span>
                  </div>
                </div>
              </div>
            </template>
            <p class="hint" v-if="tree.sensors.length === 0">该终端下无传感器</p>
          </div>
        </div>
      </div>

      <div class="modal-footer" v-if="!loading">
        <div class="modal-error" v-if="error" style="flex:1;margin-right:8px">{{ error }}</div>
        <button class="btn btn-outline" @click="emit('close')" :disabled="saving">取消</button>
        <button class="btn btn-primary" @click="handleSave" :disabled="saving || hasNonNumeric" :title="hasNonNumeric ? '存在非数字值或无匹配项，请检查后重试' : ''">
          {{ saving ? '保存中...' : '确认' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay { position: fixed; inset: 0; background: rgba(15,23,42,0.45); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-card { width: 900px; max-width: 94vw; max-height: 85vh; background: #fff; border-radius: 16px; box-shadow: 0 20px 60px rgba(15,23,42,0.18); overflow: hidden; display: flex; flex-direction: column; }
.modal-header { padding: 20px 24px 0; flex-shrink: 0; }
.modal-header h3 { margin: 0; font-size: 18px; font-weight: 700; color: #0f172a; }
.modal-body { padding: 20px 24px; overflow-y: auto; }
.modal-footer { padding: 0 24px 20px; display: flex; justify-content: flex-end; align-items: center; gap: 8px; flex-shrink: 0; }

.mapping-body { display: flex; gap: 20px; min-width: 0; }
.mapping-left { flex: 0 0 320px; min-width: 0; display: flex; flex-direction: column; gap: 14px; }
.mapping-right { flex: 1; min-width: 0; overflow: hidden; display: flex; flex-direction: column; gap: 10px; }

/* 测试 */
.test-row { display: flex; gap: 8px; align-items: center; }
.timeout-input { width: 80px; flex-shrink: 0; }
.test-result { padding: 8px 12px; border-radius: 8px; background: #f8fafc; border: 1px solid #e2e8f0; max-height: 260px; overflow: auto; }

/* 传感器树 */
.sensor-tree { border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; max-height: 360px; overflow-y: auto; }
.sensor-node { margin-bottom: 10px; }
.sensor-name { font-size: 14px; font-weight: 600; color: #0f172a; padding: 6px 0; border-bottom: 1px solid #f1f5f9; margin-bottom: 6px; }
.point-list { display: flex; flex-direction: column; gap: 6px; padding-left: 8px; }
.point-row { display: flex; align-items: center; gap: 10px; min-width: 0; }
.point-name { flex-shrink: 0; font-size: 13px; color: #475569; white-space: nowrap; }
.point-unit { font-size: 11px; color: #94a3b8; }
.json-input { flex: 1; min-width: 0; height: 30px; font-size: 13px; font-family: monospace; }
.extract-box { flex-shrink: 0; width: 100px; height: 30px; padding: 0 8px; border-radius: 6px; background: #f0fdf4; border: 1px solid #bbf7d0; font-size: 12px; font-family: monospace; color: #166534; display: flex; align-items: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.extract-err-box { background: #fef2f2; border-color: #fecaca; color: #dc2626; }

/* 时间字段 */
.time-row { display: flex; flex-direction: column; gap: 6px; margin-bottom: 2px; }
.time-input-row { display: flex; gap: 10px; align-items: center; min-width: 0; }
.time-display {
  flex-shrink: 0; height: 30px; padding: 0 8px; border-radius: 6px;
  background: #f0fdf4; border: 1px solid #bbf7d0; font-size: 12px;
  font-family: monospace; color: #166534; display: flex; align-items: center; white-space: nowrap;
}

/* 右侧 header */
.section-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.section-hint { margin: 2px 0 0; font-size: 11px; color: #94a3b8; }
.extract-err { margin: 0; font-size: 12px; color: #dc2626; }

/* 通用 */
.field { display: flex; flex-direction: column; gap: 6px; }
.field-label { font-size: 13px; font-weight: 600; color: #475569; }
.field-input, .field-select { height: 38px; padding: 0 12px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; color: #0f172a; background: #fff; outline: none; }
.field-select { cursor: pointer; }
.readonly-value { padding: 10px 12px; border-radius: 8px; background: #f8fafc; border: 1px solid #e2e8f0; font-size: 14px; color: #334155; }
.flex-1 { flex: 1; }
.hint { color: #94a3b8; font-size: 13px; text-align: center; padding: 20px; margin: 0; }
.modal-error { padding: 10px 14px; border-radius: 8px; background: #fef2f2; color: #dc2626; font-size: 13px; }

.btn { height: 38px; padding: 0 20px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; transition: background .2s ease; white-space: nowrap; }
.btn-sm { height: 32px; padding: 0 12px; font-size: 13px; }
.btn-outline { background: #f1f5f9; color: #475569; }
.btn-outline:hover { background: #e2e8f0; }
.btn-primary { background: #3b82f6; color: #fff; }
.btn-primary:hover { background: #2563eb; }
</style>
