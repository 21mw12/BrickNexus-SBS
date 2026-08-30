<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { fetchRuleTtl } from '../../../api/rule'

const props = defineProps<{ visible: boolean; ruleId: string; ruleName: string }>()
const emit = defineEmits<{ close: [] }>()
const graphEl = ref<HTMLElement | null>(null)
const loading = ref(false)
const error = ref('')
const ttl = ref('')
const view = ref<'graph' | 'source'>('graph')
let chart: any = null

type Triple = { subject: string; predicate: string; object: string; literal: boolean }

function tokenize(source: string) {
  return source.match(/"(?:\\.|[^"\\])*"(?:@[\w-]+|\^\^[\w:-]+)?|<[^>]*>|[;,\.]|[^\s;,\.]+/g) || []
}
function parseTurtle(source: string) {
  const prefixes: Record<string, string> = {}
  const body = source.replace(/@prefix\s+([\w-]*):\s*<([^>]+)>\s*\./gi, (_, key, uri) => { prefixes[key] = uri; return '' })
  const tokens = tokenize(body)
  const triples: Triple[] = []
  let i = 0
  while (i < tokens.length) {
    const subject = tokens[i++]
    if (!subject || subject === '.') continue
    let predicate = ''
    while (i < tokens.length) {
      const token = tokens[i++]!
      if (token === '.') break
      if (token === ';') { predicate = ''; continue }
      if (token === ',') continue
      if (!predicate) { predicate = token; continue }
      triples.push({ subject, predicate, object: token, literal: token.startsWith('"') || /^[-+]?\d/.test(token) || ['true', 'false'].includes(token) })
    }
  }
  const compact = (value: string) => {
    if (value === 'a') return '类型'
    const raw = value.replace(/^<|>$/g, '')
    for (const [key, uri] of Object.entries(prefixes)) if (raw.startsWith(uri)) return `${key}:${raw.slice(uri.length)}`
    return raw
  }
  return { triples, compact }
}

async function draw() {
  if (!graphEl.value || !ttl.value) return
  const echarts = await import('echarts')
  chart?.dispose()
  chart = echarts.init(graphEl.value)
  const { triples, compact } = parseTurtle(ttl.value)
  const nodeMap = new Map<string, any>()
  for (const triple of triples) {
    if (!nodeMap.has(triple.subject)) nodeMap.set(triple.subject, { id: triple.subject, name: compact(triple.subject), category: 0, symbolSize: 58 })
    if (!nodeMap.has(triple.object)) nodeMap.set(triple.object, { id: triple.object, name: compact(triple.object), category: triple.literal ? 2 : 1, symbolSize: triple.literal ? 42 : 50 })
  }
  chart.setOption({
    color: ['#3b82f6', '#10b981', '#f59e0b'],
    tooltip: { formatter: (p: any) => p.dataType === 'edge' ? `${compact(p.data.source)}<br><b>${p.data.label.show}</b><br>${compact(p.data.target)}` : p.data.name },
    legend: [{ data: ['规则资源', '关联资源', '属性值'], bottom: 8 }],
    series: [{ type: 'graph', layout: 'force', roam: true, draggable: true, animationDuration: 500,
      categories: [{ name: '规则资源' }, { name: '关联资源' }, { name: '属性值' }],
      data: [...nodeMap.values()],
      links: triples.map((t, index) => ({ id: String(index), source: t.subject, target: t.object, label: { show: compact(t.predicate), formatter: compact(t.predicate) } })),
      force: { repulsion: 430, edgeLength: [100, 180], gravity: .08 },
      label: { show: true, position: 'bottom', width: 150, overflow: 'truncate', fontSize: 11 },
      edgeLabel: { show: true, fontSize: 9, color: '#64748b', backgroundColor: 'rgba(255,255,255,.85)', padding: 2 },
      lineStyle: { color: '#94a3b8', width: 1.3, curveness: .08 }, emphasis: { focus: 'adjacency', lineStyle: { width: 3 } },
    }],
  })
}

async function load() {
  loading.value = true; error.value = ''; ttl.value = ''; view.value = 'graph'
  try { const result = await fetchRuleTtl(props.ruleId); ttl.value = result.ttl; await nextTick(); await draw() }
  catch (e: any) { error.value = e?.message || '获取 RDF 数据失败' }
  finally { loading.value = false }
}
function resize() { chart?.resize() }
watch(() => props.visible, async visible => { if (visible) { await nextTick(); load(); window.addEventListener('resize', resize) } else { window.removeEventListener('resize', resize); chart?.dispose(); chart = null } })
watch(view, async value => { if (value === 'graph') { await nextTick(); draw() } })
onBeforeUnmount(() => { window.removeEventListener('resize', resize); chart?.dispose() })
</script>

<template>
  <div v-if="visible" class="rdf-overlay" @click.self="emit('close')">
    <section class="rdf-modal">
      <header><div><h2>RDF 规则图谱</h2><p>{{ ruleName }} · 可拖动节点，滚轮缩放，拖动画布平移</p></div><button @click="emit('close')">×</button></header>
      <nav><button :class="{ active: view === 'graph' }" @click="view='graph'">关系图谱</button><button :class="{ active: view === 'source' }" @click="view='source'">TTL 原文</button><span>规则 ID：{{ ruleId }}</span></nav>
      <main><div v-show="view==='graph'" ref="graphEl" class="graph"></div><pre v-if="view==='source'">{{ ttl }}</pre><div v-if="loading" class="state">正在构建 RDF 图谱...</div><div v-else-if="error" class="state error">{{ error }}<button @click="load">重新加载</button></div><div v-else-if="!ttl" class="state">暂无 RDF 数据</div></main>
      <footer><span><i class="blue"></i>规则资源 <i class="green"></i>关联资源 <i class="orange"></i>属性值</span><button @click="emit('close')">关闭</button></footer>
    </section>
  </div>
</template>

<style scoped>
.rdf-overlay{position:fixed;inset:0;z-index:1100;display:grid;place-items:center;background:rgba(15,23,42,.52)}.rdf-modal{width:min(1120px,95vw);height:min(760px,92vh);display:flex;flex-direction:column;border-radius:16px;background:#fff;box-shadow:0 25px 70px rgba(15,23,42,.3);overflow:hidden}.rdf-modal>header{display:flex;align-items:center;justify-content:space-between;padding:18px 22px;border-bottom:1px solid #e2e8f0}.rdf-modal h2{margin:0;font-size:19px;color:#172033}.rdf-modal header p{margin:5px 0 0;color:#94a3b8;font-size:12px}.rdf-modal header button{border:0;background:none;color:#64748b;font-size:25px;cursor:pointer}.rdf-modal nav{display:flex;align-items:center;gap:5px;padding:8px 18px;background:#f8fafc;border-bottom:1px solid #e2e8f0}.rdf-modal nav button{padding:7px 13px;border:0;border-radius:7px;background:transparent;color:#64748b;cursor:pointer}.rdf-modal nav button.active{background:#fff;color:#2563eb;box-shadow:0 1px 5px rgba(15,23,42,.1)}.rdf-modal nav span{margin-left:auto;color:#94a3b8;font-size:11px}.rdf-modal main{position:relative;flex:1;min-height:0}.graph{width:100%;height:100%}pre{height:100%;margin:0;padding:20px;overflow:auto;background:#111827;color:#dbeafe;font:12px/1.7 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre-wrap}.state{position:absolute;inset:0;display:grid;place-content:center;gap:10px;text-align:center;background:rgba(255,255,255,.9);color:#64748b}.state.error{color:#b91c1c}.state button,.rdf-modal footer button{padding:7px 14px;border:0;border-radius:6px;background:#eff6ff;color:#2563eb;cursor:pointer}.rdf-modal footer{height:52px;display:flex;align-items:center;justify-content:space-between;padding:0 20px;border-top:1px solid #e2e8f0;color:#64748b;font-size:11px}.rdf-modal footer span{display:flex;align-items:center;gap:6px}.rdf-modal footer i{width:8px;height:8px;margin-left:8px;border-radius:50%}.blue{background:#3b82f6}.green{background:#10b981}.orange{background:#f59e0b}@media(max-width:700px){.rdf-modal{width:98vw;height:96vh}.rdf-modal nav span{display:none}}
</style>
