<script setup lang="ts">
import * as echarts from 'echarts'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { fetchAssetTree, type AssetTreeNode } from '../../api/asset'
import { getToken } from '../../api/auth'
import {
  createSandbox, createSandboxRule, deleteSandbox, deleteSandboxRule, downloadMeasurements,
  downloadSandbox, editSandbox, editSandboxRule, fetchBaseline, findSandboxRule, importSandbox, injectFault, listActiveFaults,
  listSandboxEvents, listSandboxRules, listSandboxes, querySandboxData, setSandboxSpeed,
  stopFault, toggleSandbox, toggleSandboxRule,
  type ActiveFault, type Sandbox, type SandboxConfig, type SandboxEvent, type SandboxPoint,
  type SandboxRule, type SandboxTerminal,
} from '../../api/sandbox'
import type { RuleConfig } from '../../api/rule'

const loading = ref(false); const error = ref(''); const notice = ref('')
const sandboxes = ref<Sandbox[]>([]); const selectedId = ref(''); const current = ref<Sandbox | null>(null)
const selectedPointId = ref(''); const chartEl = ref<HTMLElement | null>(null); let chart: echarts.ECharts | null = null
const chartRows = ref<{ tick: number; value: number | null }[]>([]); let socket: WebSocket | null = null; let reconnectTimer: number | null = null
const faults = ref<ActiveFault[]>([]); const events = ref<SandboxEvent[]>([]); const rules = ref<SandboxRule[]>([])
const lowerTab = ref<'rules'|'events'>('rules')
const speeds = [1, 2, 5, 10] as const
const points = computed(() => current.value?.config.terminals.flatMap(t => t.sensors.flatMap(s => s.points.map(p => ({ ...p, terminal: t.name, sensor: s.name })))) || [])
const selectedPoint = computed(() => points.value.find(item => item.id === selectedPointId.value))
const pointName = (id: string) => points.value.find(item => item.id === id)?.name || id

async function loadSandboxes(preferred?: string) {
  loading.value = true; error.value = ''
  try {
    const result = await listSandboxes(); sandboxes.value = result.items
    const next = preferred || selectedId.value || result.items[0]?.sandbox_id || ''
    selectedId.value = result.items.some(item => item.sandbox_id === next) ? next : (result.items[0]?.sandbox_id || '')
  } catch (e:any) { error.value = e?.message || '加载沙盒失败' } finally { loading.value = false }
}

async function loadCurrent() {
  closeSocket(); chartRows.value = []; selectedPointId.value = ''; current.value = null
  if (!selectedId.value) return
  loading.value = true
  try {
    const item = sandboxes.value.find(row => row.sandbox_id === selectedId.value)
    current.value = item ? JSON.parse(JSON.stringify(item)) : null
    if (!current.value) return
    selectedPointId.value = points.value[0]?.id || ''
    await Promise.all([refreshFaults(), refreshEvents(), refreshRules()]); connectSocket()
  } catch (e:any) { error.value = e?.message || '加载沙盒失败' } finally { loading.value = false }
}

watch(selectedId, loadCurrent)
watch(selectedPointId, () => loadChart())

async function loadChart() {
  if (!current.value || !selectedPointId.value) { chartRows.value = []; renderChart(); return }
  try {
    const end = current.value.tick + 1; const start = Math.max(0, end - 10000)
    const result = await querySandboxData(current.value.sandbox_id, { point_ids: [selectedPointId.value], start_tick: start, end_tick: Math.max(1, end), method: 'lttb', sample_count: 500 })
    const series = result.points[0]; chartRows.value = (series?.ticks || []).map((tick:number,index:number)=>({tick,value:series.values[index]})); renderChart()
  } catch (e:any) { error.value = e?.message || '加载曲线失败' }
}

function renderChart() {
  if (!chartEl.value) return; chart ||= echarts.init(chartEl.value)
  chart.setOption({ animation:false, grid:{left:52,right:22,top:35,bottom:42}, tooltip:{trigger:'axis'}, xAxis:{type:'value',name:'tick'}, yAxis:{type:'value',name:selectedPoint.value?.unit||''}, series:[{name:selectedPoint.value?.name||'',type:'line',showSymbol:false,connectNulls:false,data:chartRows.value.map(i=>[i.tick,i.value]),lineStyle:{width:2,color:'#2563eb'},areaStyle:{color:'rgba(37,99,235,.08)'}}] }, true)
}

function connectSocket() {
  if (!current.value) return
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws'; const id = current.value.sandbox_id
  socket = new WebSocket(`${protocol}://${location.host}/api/ws/sandboxes/${encodeURIComponent(id)}`)
  socket.onopen = () => socket?.send(JSON.stringify({ token: getToken() }))
  socket.onmessage = event => {
    const message = JSON.parse(event.data)
    if (message.type === 'snapshot') { current.value = message.data; return }
    if (message.type === 'sandbox_state' && current.value) current.value.state = message.state
    if (message.type === 'sandbox_speed' && current.value) current.value.config.speed = message.speed
    if (message.type === 'sandbox_event') { events.value.unshift(message.event); notice.value = '沙盒事件已更新'; refreshFaults() }
    if (message.type === 'tick' && current.value) {
      current.value.tick = message.tick
      const value = message.measurements?.find((i:any)=>i.point_id===selectedPointId.value)
      if (value) { chartRows.value.push({tick:value.tick,value:value.value}); if(chartRows.value.length>500)chartRows.value.shift(); renderChart() }
      for (const item of message.events || []) { events.value.unshift(item); if(item.event_type==='virtual_action')notice.value=`模拟动作：${item.payload.rule_name}（未真实执行）` }
      if ((message.events || []).length) refreshFaults()
    }
  }
  socket.onclose = () => { socket = null; if (selectedId.value === id) reconnectTimer = window.setTimeout(connectSocket, 2000) }
}
function closeSocket(){if(reconnectTimer){clearTimeout(reconnectTimer);reconnectTimer=null}if(socket){socket.onclose=null;socket.close();socket=null}}

async function toggleRun(){if(!current.value)return;try{const r=await toggleSandbox(current.value.sandbox_id);current.value.state=r.state;await loadSandboxes(current.value.sandbox_id)}catch(e:any){error.value=e?.message||'操作失败'}}
async function changeSpeed(event:Event){if(!current.value)return;const speed=Number((event.target as HTMLSelectElement).value) as 1|2|5|10;try{await setSandboxSpeed(current.value.sandbox_id,speed);current.value.config.speed=speed}catch(e:any){error.value=e?.message||'调速失败'}}
async function removeSandbox(){if(!current.value||!confirm(`确定删除“${current.value.sandbox_name}”及全部数据吗？`))return;try{await deleteSandbox(current.value.sandbox_id);selectedId.value='';await loadSandboxes()}catch(e:any){error.value=e?.message||'删除失败'}}

const editorOpen=ref(false); const editorMode=ref<'create'|'edit'>('create'); const editor=reactive<{sandbox_name:string;description:string;config:SandboxConfig}>({sandbox_name:'',description:'',config:{speed:1,terminals:[],sandbox_rule:[]}})
const realSensors=ref<{id:string;name:string;path:string}[]>([]); const baselineSensorId=ref(''); const baselineTerminal=ref(0)
function clone<T>(value:T):T{return JSON.parse(JSON.stringify(value))}
function openCreate(){editorMode.value='create';Object.assign(editor,{sandbox_name:'',description:'',config:{speed:1,terminals:[newTerminal()],sandbox_rule:[]}});editorOpen.value=true}
function openEdit(){if(!current.value||current.value.state)return;editorMode.value='edit';Object.assign(editor,{sandbox_name:current.value.sandbox_name,description:current.value.description||'',config:clone(current.value.config)});editorOpen.value=true}
function newTerminal():SandboxTerminal{return{name:'新终端',interval_ticks:1,sensors:[{name:'新传感器',points:[newPoint()]}]}}
function newPoint():SandboxPoint{return{id:crypto.randomUUID(),name:'新测点',unit:'',base_value:0,generator:{noise:.1,min:-100,max:100}}}
function addTerminal(){editor.config.terminals.push(newTerminal())}
function addSensor(ti:number){const terminal=editor.config.terminals[ti];if(terminal)terminal.sensors.push({name:'新传感器',points:[newPoint()]})}
function addPoint(ti:number,si:number){const sensor=editor.config.terminals[ti]?.sensors[si];if(sensor)sensor.points.push(newPoint())}
async function bindBaseline(){const terminal=editor.config.terminals[baselineTerminal.value];if(!terminal||!baselineSensorId.value)return;try{const data=await fetchBaseline(baselineSensorId.value);const available=(data.points||[]).filter((p:any)=>p.available);if(!available.length)throw new Error('该传感器最近一小时没有数据');terminal.sensors.push({name:data.sensor_name,points:available.map((p:any)=>({id:p.id,name:p.name,unit:p.unit,base_value:p.base_value,generator:p.generator}))});notice.value='已按最近一小时数据生成基准'}catch(e:any){error.value=e?.message||'获取基准失败'}}
async function saveEditor(){try{if(!editor.config.terminals.length)throw new Error('至少配置一个终端');const payload={sandbox_name:editor.sandbox_name,description:editor.description||null,config:editor.config};const saved=editorMode.value==='create'?await createSandbox(payload):await editSandbox(current.value!.sandbox_id,payload);editorOpen.value=false;await loadSandboxes(saved.sandbox_id)}catch(e:any){error.value=e?.message||'保存失败'}}

const importInput=ref<HTMLInputElement|null>(null)
async function handleImport(event:Event){const file=(event.target as HTMLInputElement).files?.[0];if(!file)return;const name=prompt('请输入导入后的沙盒名称',file.name.replace(/\.json$/i,''));if(!name)return;try{const saved=await importSandbox(file,name,'');await loadSandboxes(saved.sandbox_id)}catch(e:any){error.value=e?.message||'导入失败'}finally{(event.target as HTMLInputElement).value=''}}

const faultForm=reactive({fault_type:'drift',value:1,duration_ticks:10,continuous:false,mode:'set'})
async function refreshFaults(){if(current.value)faults.value=await listActiveFaults(current.value.sandbox_id).catch(()=>[])}
async function addFault(){if(!current.value||!selectedPointId.value)return;const key:Record<string,string>={offset:'offset',drift:'offset_per_tick',spike:'value',noise:'noise'};const parameters:any={};const parameterKey=key[faultForm.fault_type];if(faultForm.fault_type!=='stuck'&&parameterKey)parameters[parameterKey]=Number(faultForm.value);if(faultForm.fault_type==='spike')parameters.mode=faultForm.mode;try{await injectFault(current.value.sandbox_id,{fault_type:faultForm.fault_type,point_id:selectedPointId.value,duration_ticks:faultForm.continuous?null:Number(faultForm.duration_ticks),parameters});await refreshFaults()}catch(e:any){error.value=e?.message||'注入失败'}}
async function endFault(item:ActiveFault){if(!current.value)return;try{await stopFault(current.value.sandbox_id,item.event_id);await refreshFaults()}catch(e:any){error.value=e?.message||'停止失败'}}
async function refreshEvents(){if(current.value){const r=await listSandboxEvents(current.value.sandbox_id).catch(()=>({items:[],total:0}));events.value=r.items}}
async function refreshRules(){if(current.value)rules.value=await listSandboxRules(current.value.sandbox_id).catch(()=>[])}

const ruleOpen=ref(false); const ruleEditId=ref(''); const ruleForm=reactive({name:'',point_id:'',operator:'GreaterThan',threshold:30,message:'测点 {{$.point_name}} 在 tick 对应时刻触发，值为 {{$.value}}'})
function openRule(){if(current.value?.state)return;ruleEditId.value='';Object.assign(ruleForm,{name:'新沙盒规则',point_id:selectedPointId.value||points.value[0]?.id||'',operator:'GreaterThan',threshold:30,message:'测点 {{$.point_name}} 触发模拟告警，值为 {{$.value}}'});ruleOpen.value=true}
async function openRuleEdit(item:SandboxRule){if(!current.value||current.value.state)return;try{const detail=await findSandboxRule(current.value.sandbox_id,item.rule_id);const config:any=detail.config;ruleEditId.value=item.rule_id;Object.assign(ruleForm,{name:config.rule_name,point_id:config.selector.point_id,operator:config.condition.operator,threshold:Number(config.condition.right?.value??0),message:config.actions?.[0]?.params?.content||''});ruleOpen.value=true}catch(e:any){error.value=e?.message||'读取规则失败'}}
async function saveRule(){if(!current.value)return;const config:RuleConfig={rule_name:ruleForm.name,description:'沙盒独立规则',selector:{selector_id:'monitor',type:'PointIdSelector',point_id:ruleForm.point_id},condition:{type:'Comparison',operator:ruleForm.operator,left:{type:'PointValue',selector_id:'monitor'},right:{type:'ConstantValue',value:Number(ruleForm.threshold)}},trigger_policy:{trigger_count:1,trigger_duration_seconds:0,recovery_count:1,recovery_duration_seconds:0,repeat_policy:'OncePerIncident',cooldown_seconds:0,merge_window_seconds:0},actions:[{type:'LogAction',params:{level:'WARNING',content:ruleForm.message}}]};try{if(ruleEditId.value)await editSandboxRule(current.value.sandbox_id,ruleEditId.value,config);else await createSandboxRule(current.value.sandbox_id,config);ruleOpen.value=false;await refreshRules()}catch(e:any){error.value=e?.message||'保存规则失败'}}
async function flipRule(item:SandboxRule){if(!current.value)return;try{await toggleSandboxRule(current.value.sandbox_id,item.rule_id);await refreshRules()}catch(e:any){error.value=e?.message||'操作失败'}}
async function removeRule(item:SandboxRule){if(!current.value||!confirm(`删除规则“${item.rule_name}”？`))return;try{await deleteSandboxRule(current.value.sandbox_id,item.rule_id);await refreshRules()}catch(e:any){error.value=e?.message||'删除失败'}}

function flattenSensors(nodes:AssetTreeNode[],path=''):any[]{return nodes.flatMap(node=>{const next=path?`${path} / ${node.name}`:node.name;return [...((node.asset_type||node.type)==='sensor'?[{id:node.asset_id,name:node.name,path}]:[]),...flattenSensors(node.sub_assets||[],next)]})}
onMounted(async()=>{await loadSandboxes();try{realSensors.value=flattenSensors(await fetchAssetTree())}catch{}await nextTick();renderChart();window.addEventListener('resize',()=>chart?.resize())})
onBeforeUnmount(()=>{closeSocket();chart?.dispose()})
</script>

<template>
  <main class="page-content"><section class="workspace">
    <header class="page-head"><div><h1>数字孪生沙盒</h1><p>以 tick 驱动虚拟房间，安全演示故障与规则</p></div><div class="head-actions"><button class="secondary" @click="importInput?.click()">导入</button><input ref="importInput" type="file" accept="application/json" hidden @change="handleImport"><button class="primary" @click="openCreate">新建沙盒</button></div></header>
    <div v-if="error" class="message error">{{error}}<button @click="error=''">×</button></div><div v-if="notice" class="message notice">{{notice}}<button @click="notice=''">×</button></div>
    <div class="toolbar">
      <select v-model="selectedId"><option value="">请选择沙盒</option><option v-for="item in sandboxes" :key="item.sandbox_id" :value="item.sandbox_id">{{item.sandbox_name}}</option></select>
      <template v-if="current"><span class="status" :class="{running:current.state}">{{current.state?'运行中':'已暂停'}}</span><strong>tick {{current.tick}}</strong><button class="primary" @click="toggleRun">{{current.state?'暂停':'运行'}}</button><label>倍速<select :value="current.config.speed" @change="changeSpeed"><option v-for="speed in speeds" :key="speed" :value="speed">{{speed}}×</option></select></label><button :disabled="current.state" @click="openEdit">编辑结构</button><button @click="downloadSandbox(current.sandbox_id)">导出结构</button><button @click="downloadMeasurements(current.sandbox_id)">导出数据</button><button class="danger" :disabled="current.state" @click="removeSandbox">删除</button></template>
    </div>
    <div v-if="!current" class="empty"><b>请选择或创建一个沙盒</b><span>虚拟房间的数据与真实楼宇完全隔离</span></div>
    <template v-else><div class="main-grid">
      <aside class="panel tree-panel"><div class="panel-head"><h2>虚拟设备</h2><small>{{points.length}} 个测点</small></div><div class="tree"><div v-for="terminal in current.config.terminals" :key="terminal.name" class="terminal"><b>◇ {{terminal.name}}</b><small>每 {{terminal.interval_ticks}} tick</small><div v-for="sensor in terminal.sensors" :key="sensor.name" class="sensor"><span>◉ {{sensor.name}}</span><button v-for="point in sensor.points" :key="point.id" :class="{active:selectedPointId===point.id}" @click="selectedPointId=point.id"><span>{{point.name}}</span><small>{{point.unit||'无单位'}}</small></button></div></div></div></aside>
      <section class="panel chart-panel"><div class="panel-head"><div><h2>{{selectedPoint?.name||'测点趋势'}}</h2><small>基准 {{selectedPoint?.base_value??'—'}} {{selectedPoint?.unit}}</small></div><span>最近 {{chartRows.length}} 点</span></div><div ref="chartEl" class="chart"></div></section>
      <aside class="panel fault-panel"><div class="panel-head"><h2>故障注入</h2><small>仅影响虚拟测点</small></div><div class="fault-form"><label>目标<input :value="selectedPoint?.name||''" disabled></label><label>故障类型<select v-model="faultForm.fault_type"><option value="offset">固定偏移</option><option value="drift">缓慢漂移</option><option value="spike">瞬时突变</option><option value="stuck">死值</option><option value="noise">噪声增大</option></select></label><label v-if="faultForm.fault_type!=='stuck'">参数值<input v-model.number="faultForm.value" type="number" step="0.1"></label><label v-if="faultForm.fault_type==='spike'">突变方式<select v-model="faultForm.mode"><option value="set">设置为</option><option value="add">叠加</option></select></label><label class="check"><input v-model="faultForm.continuous" type="checkbox">持续到手动停止</label><label v-if="!faultForm.continuous">持续 tick<input v-model.number="faultForm.duration_ticks" type="number" min="1"></label><button class="danger solid" :disabled="!current.state||!selectedPointId" @click="addFault">注入故障</button><p v-if="!current.state" class="hint">运行沙盒后才能注入故障</p></div><div class="active-faults"><h3>生效中的故障</h3><div v-if="!faults.length" class="mini-empty">暂无</div><div v-for="item in faults" :key="item.event_id" class="fault-item"><div><b>{{item.fault_type}}</b><small>{{pointName(item.point_id)}} · tick {{item.start_tick}}{{item.end_tick===null?' 起':`–${item.end_tick}`}}</small></div><button @click="endFault(item)">停止</button></div></div></aside>
    </div><section class="panel lower"><div class="tabs"><button :class="{active:lowerTab==='rules'}" @click="lowerTab='rules'">沙盒规则</button><button :class="{active:lowerTab==='events'}" @click="lowerTab='events';refreshEvents()">事件记录</button><button v-if="lowerTab==='rules'" class="add-rule" :disabled="current.state" @click="openRule">新增规则</button></div><div v-if="lowerTab==='rules'" class="table"><div class="tr th"><span>规则名称</span><span>测点</span><span>生效 tick</span><span>状态</span><span>操作</span></div><div v-for="item in rules" :key="item.rule_id" class="tr"><span>{{item.rule_name}}</span><span>{{pointName(item.point_id||'')}}</span><span>{{item.effective_tick}}</span><span>{{item.state?'启用':'停用'}}</span><span><button :disabled="current.state" @click="openRuleEdit(item)">编辑</button><button :disabled="current.state" @click="flipRule(item)">{{item.state?'停用':'启用'}}</button><button class="text-danger" :disabled="current.state" @click="removeRule(item)">删除</button></span></div><div v-if="!rules.length" class="mini-empty">暂无沙盒规则</div></div><div v-else class="table"><div class="tr event th"><span>tick</span><span>类型</span><span>内容</span></div><div v-for="item in events" :key="item.event_id" class="tr event"><span>{{item.tick}}</span><span>{{item.event_type}}</span><span>{{item.payload.rule_name||item.payload.fault_type||item.payload.message||'—'}}</span></div><div v-if="!events.length" class="mini-empty">暂无事件</div></div></section></template>
  </section></main>

  <div v-if="editorOpen" class="modal-mask"><div class="modal wide"><header><div><h2>{{editorMode==='create'?'新建沙盒':'编辑沙盒'}}</h2><p>配置虚拟终端、传感器与测点</p></div><button @click="editorOpen=false">×</button></header><div class="modal-body"><div class="basic"><label>名称<input v-model="editor.sandbox_name" maxlength="30"></label><label>描述<input v-model="editor.description" maxlength="500"></label></div><div class="bind"><select v-model="baselineSensorId"><option value="">选择真实传感器（最近1小时基准）</option><option v-for="s in realSensors" :key="s.id" :value="s.id">{{s.path}} / {{s.name}}</option></select><select v-model.number="baselineTerminal"><option v-for="(t,i) in editor.config.terminals" :key="i" :value="i">绑定到 {{t.name}}</option></select><button @click="bindBaseline">绑定</button></div><div class="editor-tree"><article v-for="(terminal,ti) in editor.config.terminals" :key="ti" class="edit-terminal"><div class="edit-head"><input v-model="terminal.name"><label>间隔<input v-model.number="terminal.interval_ticks" type="number" min="1"> tick</label><button class="text-danger" @click="editor.config.terminals.splice(ti,1)">删除终端</button></div><section v-for="(sensor,si) in terminal.sensors" :key="si"><div class="sensor-edit"><input v-model="sensor.name"><button @click="addPoint(ti,si)">+ 测点</button><button class="text-danger" @click="terminal.sensors.splice(si,1)">删除</button></div><div v-for="(point,pi) in sensor.points" :key="point.id" class="point-edit"><input v-model="point.name" placeholder="名称"><input v-model="point.unit" placeholder="单位"><label>基值<input v-model.number="point.base_value" type="number" step="0.1"></label><label>噪声<input v-model.number="point.generator.noise" type="number" min="0" step="0.1"></label><label>最小<input v-model.number="point.generator.min" type="number"></label><label>最大<input v-model.number="point.generator.max" type="number"></label><button class="text-danger" @click="sensor.points.splice(pi,1)">×</button></div></section><button @click="addSensor(ti)">+ 添加传感器</button></article><button class="add-block" @click="addTerminal">+ 添加终端</button></div></div><footer><button @click="editorOpen=false">取消</button><button class="primary" @click="saveEditor">保存</button></footer></div></div>

  <div v-if="ruleOpen" class="modal-mask"><div class="modal"><header><div><h2>{{ruleEditId?'编辑':'新增'}}沙盒规则</h2><p>动作只在沙盒中提示，不会真实执行</p></div><button @click="ruleOpen=false">×</button></header><div class="modal-body rule-form"><label>规则名称<input v-model="ruleForm.name"></label><label>监控测点<select v-model="ruleForm.point_id"><option v-for="p in points" :key="p.id" :value="p.id">{{p.sensor}} / {{p.name}}</option></select></label><div class="condition"><span>测点值</span><select v-model="ruleForm.operator"><option value="GreaterThan">大于</option><option value="GreaterThanOrEqual">大于等于</option><option value="LessThan">小于</option><option value="LessThanOrEqual">小于等于</option><option value="Equal">等于</option><option value="NotEqual">不等于</option></select><input v-model.number="ruleForm.threshold" type="number"></div><label>模拟提示内容<textarea v-model="ruleForm.message" rows="3"></textarea></label></div><footer><button @click="ruleOpen=false">取消</button><button class="primary" @click="saveRule">保存规则</button></footer></div></div>
</template>

<style scoped>
*{box-sizing:border-box}.page-content{flex:1;min-width:0;padding:26px 30px;color:#172033;overflow:auto}.workspace{min-height:calc(100vh - 52px)}button,select,input,textarea{font:inherit}.page-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}.page-head h1{margin:0 0 4px;font-size:24px}.page-head p,.modal header p{margin:0;color:#8492a6;font-size:13px}.head-actions,.toolbar{display:flex;align-items:center;gap:9px}.toolbar{min-height:56px;padding:10px 14px;margin-bottom:16px;border:1px solid #e6ebf2;border-radius:13px;background:#fff;box-shadow:0 4px 16px rgba(15,23,42,.04);flex-wrap:wrap}.toolbar>select{min-width:210px}.toolbar strong{font-size:14px}.toolbar label{display:flex;align-items:center;gap:6px;color:#64748b;font-size:12px}.toolbar button,.head-actions button,.bind button,.edit-head button,.sensor-edit button,.edit-terminal>button,.tabs button,.fault-item button,.tr button,footer button{height:34px;padding:0 13px;border:1px solid #dbe3ee;border-radius:7px;background:#fff;color:#475569;cursor:pointer}.toolbar button:disabled,.tabs button:disabled,.tr button:disabled{opacity:.45;cursor:not-allowed}.primary{border-color:#2563eb!important;background:#2563eb!important;color:#fff!important}.danger{color:#dc2626!important}.danger.solid{border-color:#dc2626!important;background:#dc2626!important;color:#fff!important}.status{padding:5px 9px;border-radius:99px;background:#f1f5f9;color:#64748b;font-size:11px}.status.running{background:#dcfce7;color:#15803d}.message{display:flex;justify-content:space-between;padding:10px 13px;margin-bottom:12px;border-radius:8px;font-size:12px}.message.error{background:#fef2f2;color:#b91c1c}.message.notice{background:#eff6ff;color:#1d4ed8}.message button{border:0;background:none;color:inherit}.main-grid{display:grid;grid-template-columns:245px minmax(400px,1fr) 280px;gap:15px;height:480px}.panel{border:1px solid #e6ebf2;border-radius:13px;background:#fff;box-shadow:0 4px 16px rgba(15,23,42,.04);overflow:hidden}.panel-head{min-height:58px;display:flex;align-items:center;justify-content:space-between;padding:12px 15px;border-bottom:1px solid #edf1f6}.panel-head h2{margin:0;font-size:14px}.panel-head small,.panel-head span{color:#94a3b8;font-size:10px}.tree{height:calc(100% - 58px);padding:10px;overflow:auto}.terminal{margin-bottom:10px}.terminal>b{display:inline-block;font-size:12px}.terminal>small{float:right;color:#94a3b8;font-size:9px}.sensor{padding:7px 0 0 15px}.sensor>span{display:block;margin-bottom:3px;color:#64748b;font-size:11px}.sensor button{width:100%;display:flex;justify-content:space-between;padding:7px;border:0;border-radius:6px;background:transparent;color:#475569;cursor:pointer}.sensor button:hover,.sensor button.active{background:#eff6ff;color:#1d4ed8}.sensor button small{font-size:9px;color:#94a3b8}.chart{height:calc(100% - 58px)}.fault-panel{overflow:auto}.fault-form,.active-faults{padding:13px}.fault-form label,.rule-form label,.basic label{display:flex;flex-direction:column;gap:5px;margin-bottom:10px;color:#64748b;font-size:11px}.fault-form input,.fault-form select,.rule-form input,.rule-form select,.rule-form textarea,.basic input,.bind select,.edit-terminal input{padding:8px;border:1px solid #dbe3ee;border-radius:7px;outline:none;background:#fff}.fault-form .check{flex-direction:row;align-items:center}.fault-form button{width:100%;height:35px;border:0;border-radius:7px}.hint,.mini-empty{color:#94a3b8;font-size:10px;text-align:center}.active-faults{border-top:1px solid #edf1f6}.active-faults h3{margin:0 0 8px;font-size:12px}.fault-item{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid #f1f5f9}.fault-item b,.fault-item small{display:block;font-size:10px}.fault-item small{margin-top:2px;color:#94a3b8}.fault-item button{height:26px;padding:0 8px;color:#dc2626;font-size:10px}.lower{margin-top:15px;min-height:220px}.tabs{display:flex;gap:4px;padding:8px 12px;border-bottom:1px solid #edf1f6}.tabs button{border:0}.tabs button.active{background:#2563eb;color:#fff}.tabs .add-rule{margin-left:auto;border:1px solid #dbe3ee}.table{padding:6px 12px}.tr{display:grid;grid-template-columns:2fr 2fr 1fr 1fr 1.4fr;align-items:center;min-height:40px;border-bottom:1px solid #f1f5f9;font-size:11px}.tr.event{grid-template-columns:100px 180px 1fr}.tr.th{color:#94a3b8;font-weight:600}.tr button{height:26px;padding:0 8px;margin-right:5px;font-size:10px}.text-danger{color:#dc2626!important}.empty{height:420px;display:flex;flex-direction:column;align-items:center;justify-content:center;border:1px dashed #cbd5e1;border-radius:13px;background:#fff;color:#94a3b8}.empty b{margin-bottom:7px;color:#475569}.modal-mask{position:fixed;inset:0;z-index:1000;display:grid;place-items:center;padding:24px;background:rgba(15,23,42,.45)}.modal{width:min(520px,95vw);max-height:90vh;display:flex;flex-direction:column;border-radius:14px;background:#fff;box-shadow:0 24px 70px rgba(15,23,42,.3)}.modal.wide{width:min(1000px,96vw)}.modal header,.modal footer{display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid #edf1f6}.modal header h2{margin:0 0 3px;font-size:18px}.modal header>button{border:0;background:none;font-size:23px}.modal-body{padding:18px 20px;overflow:auto}.modal footer{justify-content:flex-end;gap:8px;border-top:1px solid #edf1f6;border-bottom:0}.basic{display:grid;grid-template-columns:1fr 2fr;gap:12px}.bind{display:flex;gap:8px;padding:10px;margin-bottom:12px;border-radius:8px;background:#f8fafc}.bind select:first-child{flex:1}.edit-terminal{padding:12px;margin-bottom:10px;border:1px solid #dbe3ee;border-radius:10px}.edit-head,.sensor-edit,.point-edit{display:flex;align-items:center;gap:8px}.edit-head>input,.sensor-edit>input{flex:1;font-weight:600}.edit-head label{display:flex;align-items:center;gap:4px;font-size:10px}.edit-head label input{width:70px}.sensor-edit{padding:10px 0 6px 15px}.point-edit{padding:5px 0 5px 30px}.point-edit>input{width:100px}.point-edit label{display:flex;align-items:center;gap:3px;color:#64748b;font-size:9px}.point-edit label input{width:70px}.point-edit button{border:0;background:none}.add-block{width:100%;border-style:dashed!important}.condition{display:grid;grid-template-columns:1fr 1fr 1fr;align-items:center;gap:8px;margin-bottom:12px}.condition span{padding:8px;border-radius:7px;background:#f1f5f9;color:#64748b;font-size:12px}.condition select,.condition input{padding:8px;border:1px solid #dbe3ee;border-radius:7px}@media(max-width:1150px){.main-grid{grid-template-columns:220px 1fr;height:auto}.fault-panel{grid-column:1/-1}.chart-panel{height:420px}}@media(max-width:760px){.page-content{padding:18px}.main-grid{grid-template-columns:1fr}.tree-panel,.chart-panel{height:400px}.basic{grid-template-columns:1fr}.point-edit{flex-wrap:wrap}.toolbar{align-items:stretch}.toolbar>select{width:100%}}
</style>
