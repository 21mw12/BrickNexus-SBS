<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import {
  fetchBaseline, fetchSandboxModelSensors,
  type Sandbox, type SandboxBaselineSource, type SandboxConfig,
  type SandboxPoint, type SandboxSensor, type SandboxSensorModel,
} from '../../api/sandbox'
import { notifyError } from '../../utils/notification'

const props = defineProps<{ visible: boolean; mode: 'create' | 'edit'; sandbox: Sandbox | null; models: SandboxSensorModel[]; saving?: boolean }>()
const emit = defineEmits<{ close: []; submit: [payload: { sandbox_name: string; description: string | null; config: SandboxConfig }] }>()

type DraftSensor = SandboxSensor & { _key: string; baseline_mode: 'manual' | 'reference'; source_sensor_id: string; sources: SandboxBaselineSource[]; loading_sources: boolean; loading_baseline: boolean; advanced: boolean; baseline_note: string }
type DraftTerminal = { name: string; _key: string; sensors: DraftSensor[] }

const step = ref(1)
const error = ref('')
const form = reactive<{ sandbox_name: string; description: string; speed: 1 | 2 | 5 | 10; terminals: DraftTerminal[] }>({ sandbox_name: '', description: '', speed: 1, terminals: [] })
const stepNames = ['基本信息', '设备配置', '基准设置']
const modelMap = computed(() => new Map(props.models.map(item => [item.model_id, item])))

function key() { return crypto.randomUUID() }
function defaultGenerator(base = 0) { return { noise: 0.1, min: base - 1, max: base + 1 } }
function draftPoint(point: SandboxSensorModel['points'][number], existing?: SandboxPoint): SandboxPoint {
  return {
    id: existing?.id || key(), source_point_id: point.point_id,
    name: point.point_name, unit: point.point_unit || '',
    base_value: existing?.base_value ?? 0,
    generator: existing ? { ...existing.generator } : defaultGenerator(),
  }
}
function draftSensor(sensor?: SandboxSensor): DraftSensor {
  return {
    name: sensor?.name || '', model_id: sensor?.model_id || null,
    points: (sensor?.points || []).map(point => ({ ...point, generator: { ...point.generator } })),
    _key: key(), baseline_mode: 'manual', source_sensor_id: '', sources: [],
    loading_sources: false, loading_baseline: false, advanced: false,
    baseline_note: sensor?.model_id ? '' : '旧配置需要重新选择传感器型号',
  }
}
function draftTerminal(terminal?: Sandbox['config']['terminals'][number]): DraftTerminal {
  return { name: terminal?.name || '', _key: key(), sensors: (terminal?.sensors || []).map(item => draftSensor(item)) }
}

watch(() => props.visible, visible => {
  if (!visible) return
  step.value = 1; error.value = ''
  if (props.mode === 'edit' && props.sandbox) {
    form.sandbox_name = props.sandbox.sandbox_name
    form.description = props.sandbox.description || ''
    form.speed = props.sandbox.config.speed
    form.terminals = props.sandbox.config.terminals.map(item => draftTerminal(item))
  } else {
    form.sandbox_name = ''; form.description = ''; form.speed = 1
    form.terminals = [draftTerminal()]
  }
}, { immediate: true })

watch(error, value => {
  if (!value) return
  notifyError(value, props.mode === 'create' ? '无法创建沙盒' : '无法保存沙盒')
  error.value = ''
})

function addTerminal() { form.terminals.push(draftTerminal()) }
function addSensor(terminal: DraftTerminal) { terminal.sensors.push(draftSensor()) }
function selectModel(sensor: DraftSensor) {
  const model = sensor.model_id ? modelMap.value.get(sensor.model_id) : undefined
  sensor.points = model?.points.map(point => draftPoint(point)) || []
  sensor.sources = []; sensor.source_sensor_id = ''; sensor.baseline_mode = 'manual'
  sensor.baseline_note = model ? '' : '请选择传感器型号'
  if (!sensor.name && model) sensor.name = model.model_name
}
async function loadSources(sensor: DraftSensor) {
  if (!sensor.model_id || sensor.sources.length || sensor.loading_sources) return
  sensor.loading_sources = true
  try { sensor.sources = await fetchSandboxModelSensors(sensor.model_id) }
  catch (e: any) { error.value = e?.message || '加载同型号真实传感器失败' }
  finally { sensor.loading_sources = false }
}
async function applyReference(sensor: DraftSensor) {
  if (!sensor.source_sensor_id) return
  sensor.loading_baseline = true; sensor.baseline_note = ''
  try {
    const baseline = await fetchBaseline(sensor.source_sensor_id)
    if (baseline.model_id !== sensor.model_id) throw new Error('真实传感器型号与虚拟传感器不一致')
    const byDefinition = new Map(baseline.points.map(point => [point.source_definition_id, point]))
    let fallbackCount = 0
    sensor.points = sensor.points.map(point => {
      const source = byDefinition.get(point.source_point_id || '')
      if (!source) return point
      if (!source.available) fallbackCount += 1
      return { ...point, base_value: source.base_value, generator: { ...source.generator } }
    })
    sensor.baseline_note = fallbackCount
      ? `${fallbackCount} 个测点最近一小时无数据，已采用默认基线 0`
      : `已读取 ${baseline.sensor_name} 最近一小时数据`
  } catch (e: any) { error.value = e?.message || '读取历史基准失败' }
  finally { sensor.loading_baseline = false }
}
function useMode(sensor: DraftSensor) {
  sensor.baseline_note = ''
  if (sensor.baseline_mode === 'reference') void loadSources(sensor)
}
function normalizeBounds(point: SandboxPoint) {
  if (!Number.isFinite(point.base_value)) return
  if (point.base_value < point.generator.min) point.generator.min = point.base_value - 1
  if (point.base_value > point.generator.max) point.generator.max = point.base_value + 1
}
function validate(targetStep = step.value) {
  error.value = ''
  if (!form.sandbox_name.trim()) { error.value = '请输入沙盒名称'; return false }
  if (targetStep >= 2) {
    if (!form.terminals.length) { error.value = '至少添加一个终端'; return false }
    for (const terminal of form.terminals) {
      if (!terminal.name.trim()) { error.value = '请填写终端名称'; return false }
      if (!terminal.sensors.length) { error.value = `终端“${terminal.name}”至少添加一个传感器`; return false }
      for (const sensor of terminal.sensors) {
        if (!sensor.name.trim()) { error.value = '请填写虚拟传感器名称'; return false }
        if (!sensor.model_id || !modelMap.value.has(sensor.model_id)) { error.value = `传感器“${sensor.name || '未命名'}”必须选择型号`; return false }
        if (!sensor.points.length) { error.value = `传感器“${sensor.name}”的型号没有测点`; return false }
      }
    }
  }
  if (targetStep >= 3) {
    for (const terminal of form.terminals) for (const sensor of terminal.sensors) for (const point of sensor.points) {
      const values = [point.base_value, point.generator.noise, point.generator.min, point.generator.max]
      if (!values.every(Number.isFinite)) { error.value = `测点“${point.name}”的生成参数不完整`; return false }
      if (point.generator.noise < 0 || point.generator.min > point.generator.max || point.base_value < point.generator.min || point.base_value > point.generator.max) {
        error.value = `测点“${point.name}”的基值必须位于上下限内，且噪声不能为负`; return false
      }
    }
  }
  return true
}
function next() { if (validate(step.value)) step.value = Math.min(3, step.value + 1) }
function submit() {
  if (!validate(3)) return
  emit('submit', {
    sandbox_name: form.sandbox_name.trim(), description: form.description.trim() || null,
    config: {
      speed: form.speed,
      terminals: form.terminals.map(terminal => ({
        name: terminal.name.trim(),
        sensors: terminal.sensors.map(sensor => ({
          name: sensor.name.trim(), model_id: sensor.model_id,
          points: sensor.points.map(point => ({ ...point, generator: { ...point.generator } })),
        })),
      })),
      sandbox_rule: props.mode === 'edit' ? (props.sandbox?.config.sandbox_rule || []) : [],
    },
  })
}
</script>

<template>
  <div v-if="visible" class="overlay" @mousedown.self="emit('close')">
    <section class="editor">
      <header><div><span class="eyebrow">VIRTUAL ROOM</span><h2>{{ mode === 'create' ? '创建数字孪生沙盒' : '编辑沙盒结构' }}</h2><p>传感器测点由型号定义，数据与真实楼宇完全隔离</p></div><button class="close" @click="emit('close')">×</button></header>
      <nav class="steps"><button v-for="(name,index) in stepNames" :key="name" :class="{active:step===index+1,done:step>index+1}" @click="index+1<step&&(step=index+1)"><i>{{step>index+1?'✓':index+1}}</i><span>{{name}}</span></button></nav>
      <div class="body">
        <section v-if="step===1" class="basic-grid">
          <label><span>沙盒名称 *</span><input v-model="form.sandbox_name" maxlength="30" placeholder="例如：暖通规则演示房间"></label>
          <label><span>初始倍速</span><select v-model="form.speed"><option :value="1">1× · 30秒/tick</option><option :value="2">2× · 15秒/tick</option><option :value="5">5× · 6秒/tick</option><option :value="10">10× · 3秒/tick</option></select></label>
          <label class="wide"><span>描述</span><textarea v-model="form.description" maxlength="500" rows="5" placeholder="说明这个沙盒用于验证哪些故障或规则"></textarea></label>
          <div class="time-note wide"><b>统一时间语义</b><span>所有测点每个 tick 生成一次数据，全部规则也在每个 tick 校验一次。</span></div>
        </section>
        <section v-else-if="step===2" class="topology">
          <article v-for="(terminal,ti) in form.terminals" :key="terminal._key" class="terminal-card">
            <header><div><i>终端 {{String(ti+1).padStart(2,'0')}}</i><input v-model="terminal.name" maxlength="100" placeholder="终端名称"></div><button class="danger" @click="form.terminals.splice(ti,1)">删除终端</button></header>
            <div class="sensor-list">
              <article v-for="(sensor,si) in terminal.sensors" :key="sensor._key" class="sensor-card">
                <div class="sensor-fields"><label><span>虚拟传感器名称</span><input v-model="sensor.name" maxlength="100" placeholder="自定义显示名称"></label><label><span>传感器型号</span><select v-model="sensor.model_id" @change="selectModel(sensor)"><option :value="null">请选择现有型号</option><option v-for="model in models" :key="model.model_id" :value="model.model_id">{{model.model_name}} · {{model.sensor_type||'未分类'}}</option></select></label><button class="icon-danger" title="删除传感器" @click="terminal.sensors.splice(si,1)">×</button></div>
                <div v-if="sensor.points.length" class="point-preview"><span v-for="point in sensor.points" :key="point.source_point_id||point.id"><b>{{point.name}}</b><small>{{point.unit||'无单位'}}</small></span></div>
                <p v-else>{{sensor.baseline_note||'选择型号后自动载入该型号的全部测点'}}</p>
              </article>
              <button class="add-sensor" @click="addSensor(terminal)">＋ 添加传感器</button>
            </div>
          </article>
          <button class="add-terminal" @click="addTerminal">＋ 添加虚拟终端</button>
        </section>
        <section v-else class="baselines">
          <template v-for="terminal in form.terminals" :key="terminal._key"><article v-for="sensor in terminal.sensors" :key="sensor._key" class="baseline-card">
            <header><div><small>{{terminal.name}}</small><h3>{{sensor.name}}</h3></div><span>{{modelMap.get(sensor.model_id||'')?.model_name}}</span></header>
            <div class="mode-switch"><button :class="{active:sensor.baseline_mode==='manual'}" @click="sensor.baseline_mode='manual';useMode(sensor)"><b>手动设置</b><small>直接填写每个测点的基准值</small></button><button :class="{active:sensor.baseline_mode==='reference'}" @click="sensor.baseline_mode='reference';useMode(sensor)"><b>真实数据</b><small>读取同型号传感器最近一小时</small></button></div>
            <div v-if="sensor.baseline_mode==='reference'" class="source-row"><select v-model="sensor.source_sensor_id" :disabled="sensor.loading_sources"><option value="">{{sensor.loading_sources?'正在加载...':'选择同型号真实传感器'}}</option><option v-for="source in sensor.sources" :key="source.sensor_id" :value="source.sensor_id">{{source.path||source.sensor_name}}</option></select><button :disabled="!sensor.source_sensor_id||sensor.loading_baseline" @click="applyReference(sensor)">{{sensor.loading_baseline?'读取中...':'读取基准'}}</button></div>
            <p v-if="sensor.baseline_note" class="note">{{sensor.baseline_note}}</p>
            <div class="point-values"><div v-for="point in sensor.points" :key="point.id" class="point-value"><div><b>{{point.name}}</b><small>{{point.unit||'无单位'}}</small></div><label>基准值<input v-model.number="point.base_value" type="number" step="any" @change="normalizeBounds(point)"></label><button @click="sensor.advanced=!sensor.advanced">{{sensor.advanced?'收起参数':'高级参数'}}</button><div v-if="sensor.advanced" class="advanced"><label>噪声<input v-model.number="point.generator.noise" type="number" min="0" step="any"></label><label>最小值<input v-model.number="point.generator.min" type="number" step="any"></label><label>最大值<input v-model.number="point.generator.max" type="number" step="any"></label></div></div></div>
          </article></template>
        </section>
      </div>
      <footer><span>步骤 {{step}} / 3</span><div><button v-if="step>1" @click="step--">上一步</button><button @click="emit('close')">取消</button><button v-if="step<3" class="primary" @click="next">下一步</button><button v-else class="primary" :disabled="saving" @click="submit">{{saving?'保存中...':'保存沙盒'}}</button></div></footer>
    </section>
  </div>
</template>

<style scoped>
*{box-sizing:border-box}.overlay{position:fixed;inset:0;z-index:1100;display:grid;place-items:center;padding:24px;background:rgba(15,23,42,.5);backdrop-filter:blur(3px)}.editor{width:min(1040px,96vw);height:min(760px,94vh);display:flex;flex-direction:column;overflow:hidden;border:1px solid rgba(255,255,255,.8);border-radius:20px;background:#fff;box-shadow:0 28px 80px rgba(15,23,42,.3)}.editor>header{display:flex;align-items:center;justify-content:space-between;padding:22px 28px 18px;background:linear-gradient(135deg,#f7fbff,#fff);border-bottom:1px solid #e8eef5}.eyebrow{display:block;margin-bottom:5px;color:#3b82f6;font-size:9px;font-weight:800;letter-spacing:.16em}.editor h2{margin:0 0 5px;color:#0f172a;font-size:21px}.editor header p{margin:0;color:#8492a6;font-size:12px}.close{width:36px;height:36px;border:0;border-radius:10px;color:#64748b;background:#eef2f7;font-size:23px;cursor:pointer}.steps{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;padding:13px 28px;border-bottom:1px solid #edf1f6;background:#fbfdff}.steps button{display:flex;align-items:center;gap:9px;padding:10px 12px;border:1px solid transparent;border-radius:10px;color:#94a3b8;background:transparent;text-align:left;cursor:pointer}.steps button.active{border-color:#bfdbfe;color:#1d4ed8;background:#eff6ff}.steps button.done{color:#047857}.steps i{width:25px;height:25px;display:grid;place-items:center;border-radius:50%;color:#64748b;background:#e2e8f0;font-style:normal;font-size:10px;font-weight:700}.steps .active i{color:#fff;background:#3b82f6}.steps .done i{color:#fff;background:#10b981}.steps span{font-size:12px;font-weight:700}.body{flex:1;min-height:0;padding:22px 28px;overflow:auto;background:#f8fafc}.alert{margin-bottom:14px;padding:10px 13px;border:1px solid #fecaca;border-radius:9px;color:#b91c1c;background:#fff}.basic-grid{display:grid;grid-template-columns:2fr 1fr;gap:18px;max-width:780px;margin:15px auto}.basic-grid label{display:flex;flex-direction:column;gap:7px;color:#475569;font-size:12px;font-weight:650}.basic-grid input,.basic-grid select,.basic-grid textarea,.sensor-fields input,.sensor-fields select,.source-row select,.point-value input{width:100%;padding:10px 12px;border:1px solid #d7e0eb;border-radius:9px;color:#1e293b;background:#fff;outline:none}.basic-grid input,.basic-grid select{height:42px}.basic-grid textarea{resize:none}.basic-grid input:focus,.basic-grid select:focus,.basic-grid textarea:focus,.sensor-fields input:focus,.sensor-fields select:focus,.point-value input:focus{border-color:#60a5fa;box-shadow:0 0 0 3px rgba(59,130,246,.11)}.wide{grid-column:1/-1}.time-note{display:flex;flex-direction:column;gap:5px;padding:15px;border:1px solid #dbeafe;border-radius:10px;color:#64748b;background:#eff6ff;font-size:12px}.time-note b{color:#1d4ed8}.topology,.baselines{display:flex;flex-direction:column;gap:13px}.terminal-card,.baseline-card{overflow:hidden;border:1px solid #e2e8f0;border-radius:13px;background:#fff;box-shadow:0 2px 8px rgba(15,23,42,.03)}.terminal-card>header,.baseline-card>header{display:flex;align-items:center;justify-content:space-between;padding:13px 16px;border-bottom:1px solid #edf1f6;background:#fbfdff}.terminal-card>header>div{display:flex;align-items:center;gap:11px}.terminal-card header i{color:#2563eb;font-size:10px;font-style:normal;font-weight:800}.terminal-card header input{width:260px;padding:8px 10px;border:1px solid #dbe3ee;border-radius:7px;font-weight:650}.danger,.icon-danger{border:0;color:#dc2626;background:#fef2f2;cursor:pointer}.danger{padding:7px 10px;border-radius:7px}.sensor-list{padding:12px 16px}.sensor-card{margin-bottom:9px;padding:12px;border:1px solid #e5eaf1;border-radius:10px}.sensor-fields{display:grid;grid-template-columns:1fr 1.2fr 30px;gap:10px;align-items:end}.sensor-fields label{display:flex;flex-direction:column;gap:5px;color:#64748b;font-size:10px;font-weight:650}.sensor-fields input,.sensor-fields select{height:38px;padding:0 10px}.icon-danger{height:38px;border-radius:8px;font-size:18px}.point-preview{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px;padding-top:10px;border-top:1px dashed #e2e8f0}.point-preview span{display:flex;gap:5px;padding:5px 8px;border-radius:6px;color:#334155;background:#f1f5f9;font-size:10px}.point-preview small{color:#94a3b8}.sensor-card>p{margin:9px 0 0;color:#94a3b8;font-size:10px}.add-sensor,.add-terminal{height:38px;border:1px dashed #bfdbfe;border-radius:9px;color:#2563eb;background:#f8fbff;cursor:pointer}.add-sensor{width:100%}.add-terminal{height:44px}.baseline-card>header h3{margin:3px 0 0;font-size:15px}.baseline-card>header small{color:#94a3b8}.baseline-card>header>span{padding:5px 9px;border-radius:9px;color:#2563eb;background:#eff6ff;font-size:10px}.mode-switch{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:13px 15px 0}.mode-switch button{display:flex;flex-direction:column;gap:3px;padding:10px 12px;border:1px solid #e2e8f0;border-radius:9px;color:#64748b;background:#fff;text-align:left;cursor:pointer}.mode-switch button.active{border-color:#60a5fa;color:#1d4ed8;background:#eff6ff}.mode-switch small{color:#94a3b8}.source-row{display:flex;gap:8px;padding:12px 15px 0}.source-row select{flex:1;height:39px;padding:0 10px}.source-row button,.point-value>button{padding:0 12px;border:1px solid #bfdbfe;border-radius:7px;color:#2563eb;background:#eff6ff;cursor:pointer}.note{margin:10px 15px 0;padding:8px 10px;border-radius:7px;color:#9a6700;background:#fffbeb;font-size:10px}.point-values{padding:12px 15px 15px}.point-value{display:grid;grid-template-columns:minmax(150px,1fr) 180px 84px;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid #f1f5f9}.point-value:last-child{border-bottom:0}.point-value>div:first-child{display:flex;flex-direction:column;gap:3px}.point-value b{font-size:12px}.point-value small{color:#94a3b8;font-size:9px}.point-value label{display:flex;align-items:center;gap:7px;color:#64748b;font-size:10px}.point-value label input{height:34px;padding:0 8px}.point-value>button{height:32px}.advanced{grid-column:1/-1;display:grid!important;grid-template-columns:repeat(3,1fr);gap:12px!important;padding:10px 12px;border-radius:8px;background:#f8fafc}.editor>footer{display:flex;align-items:center;justify-content:space-between;padding:15px 28px;border-top:1px solid #e2e8f0;background:#fff}.editor>footer>span{color:#94a3b8;font-size:11px}.editor>footer>div{display:flex;gap:8px}.editor>footer button{min-width:86px;height:38px;border:1px solid #dbe3ee;border-radius:8px;color:#475569;background:#fff;cursor:pointer}.editor>footer .primary{border-color:#3b82f6;color:#fff;background:#3b82f6;box-shadow:0 3px 9px rgba(59,130,246,.2)}button:disabled{opacity:.5;cursor:not-allowed}@media(max-width:760px){.overlay{padding:8px}.editor{height:98vh}.steps{padding:10px}.steps button{justify-content:center}.steps span{display:none}.body{padding:14px}.basic-grid{grid-template-columns:1fr}.wide{grid-column:auto}.sensor-fields,.point-value{grid-template-columns:1fr}.advanced{grid-template-columns:1fr!important}.terminal-card>header>div{align-items:flex-start;flex-direction:column}.terminal-card header input{width:100%}}
</style>
