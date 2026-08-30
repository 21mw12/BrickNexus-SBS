<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { DataZoomComponent, GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsType } from 'echarts/core'
import { fetchAssetTree, sortAssetTreeForDisplay, type AssetTreeNode } from '../../api/asset'
import { queryHistory, type HistoryQueryResult } from '../../api/history'
import { fetchTerminalTree, type PointInfo, type TerminalTree } from '../../api/request'
import { isMenuGroup, menuConfig } from '../../config/menu'

echarts.use([LineChart, GridComponent, TooltipComponent, DataZoomComponent, CanvasRenderer])

interface SelectedPoint extends PointInfo {
  sensor_name: string
  terminal_name: string
  room_name: string
  path: string
}

const route = useRoute()
const router = useRouter()
const siblings = computed(() => {
  for (const entry of menuConfig) if (isMenuGroup(entry) && entry.children.some(item => item.route === route.path)) return entry.children
  return []
})

const assetTree = ref<AssetTreeNode[]>([])
const treeLoading = ref(true)
const expanded = reactive(new Set<string>())
const terminalTrees = reactive(new Map<string, TerminalTree>())
const terminalLoading = reactive(new Set<string>())
const selectedPoints = ref<SelectedPoint[]>([])
const result = ref<HistoryQueryResult | null>(null)
const querying = ref(false)
const error = ref('')
const chartEl = ref<HTMLDivElement | null>(null)
let chart: EChartsType | null = null
let resizeObserver: ResizeObserver | null = null

const mode = ref<'value' | 'change'>('value')
const smooth = ref(true)
const showSymbol = ref(false)
const showArea = ref(false)
const sampleCount = ref(500)

function datePart(date: Date) {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}
const now = new Date()
const roundedStart = new Date(now.getTime() - 24 * 60 * 60 * 1000)
roundedStart.setMinutes(Math.floor(roundedStart.getMinutes() / 15) * 15, 0, 0)
const startDate = ref(datePart(roundedStart))
const startHour = ref(roundedStart.getHours())
const startMinute = ref(roundedStart.getMinutes())
const endDate = ref(datePart(now))
const endHour = ref(now.getHours())
const endMinute = ref(Math.floor(now.getMinutes() / 5) * 5)
const openTimePicker = ref<'start' | 'end' | null>(null)
const hours = Array.from({ length: 24 }, (_, index) => index)
const startMinutes = [0, 15, 30, 45]
const endMinutes = Array.from({ length: 12 }, (_, index) => index * 5)

const padTime = (value: number) => String(value).padStart(2, '0')
function dateTimeValue(date: string, hour: number, minute: number) { return `${date}T${padTime(hour)}:${padTime(minute)}` }
function apiTime(date: string, hour: number, minute: number) { return `${date} ${padTime(hour)}:${padTime(minute)}:00` }
function toggle(id: string) { expanded.has(id) ? expanded.delete(id) : expanded.add(id) }
function pointSelected(id: string) { return selectedPoints.value.some(point => point.point_id === id) }

async function toggleTerminal(terminal: AssetTreeNode, path: string) {
  toggle(terminal.asset_id)
  if (!expanded.has(terminal.asset_id) || terminalTrees.has(terminal.asset_id) || terminalLoading.has(terminal.asset_id)) return
  terminalLoading.add(terminal.asset_id)
  try {
    const data = await fetchTerminalTree(terminal.asset_id)
    terminalTrees.set(terminal.asset_id, { ...data, terminal_name: data.terminal_name || terminal.name })
  } catch (e: any) { error.value = e?.message || `加载终端「${terminal.name}」测点失败` }
  finally { terminalLoading.delete(terminal.asset_id) }
}

function togglePoint(point: PointInfo, sensorName: string, terminal: TerminalTree, roomName: string, path: string) {
  const index = selectedPoints.value.findIndex(item => item.point_id === point.point_id)
  if (index >= 0) { selectedPoints.value.splice(index, 1); result.value = null; return }
  if (selectedPoints.value.length >= 10) { error.value = '一次最多选择 10 个测点'; return }
  selectedPoints.value.push({ ...point, sensor_name: sensorName, terminal_name: terminal.terminal_name, room_name: roomName, path })
  result.value = null
}
function removePoint(id: string) { selectedPoints.value = selectedPoints.value.filter(point => point.point_id !== id); result.value = null }
function pointStats(id: string) { return result.value?.points.find(point => point.point_id === id) }

function historyTimestamp(value: string) {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})$/)
  if (!match) return Date.parse(value.replace(' ', 'T'))
  const [, year, month, day, hour, minute, second] = match
  return new Date(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute), Number(second)).getTime()
}

function validateQuery() {
  if (!selectedPoints.value.length) return '请至少选择一个测点'
  const start = new Date(dateTimeValue(startDate.value, startHour.value, startMinute.value))
  const end = new Date(dateTimeValue(endDate.value, endHour.value, endMinute.value))
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return '请选择有效的开始和结束时间'
  if (end <= start) return '结束时间必须晚于开始时间'
  const duration = end.getTime() - start.getTime()
  if (duration < 15 * 60 * 1000) return '查询范围不能少于 15 分钟'
  if (duration > 31 * 24 * 60 * 60 * 1000) return '查询范围不能超过 31 天'
  if (!Number.isInteger(sampleCount.value) || sampleCount.value < 100 || sampleCount.value > 1000) return '采样数量必须为 100～1000 的整数'
  return ''
}

async function runQuery() {
  error.value = validateQuery()
  if (error.value) return
  querying.value = true
  try {
    result.value = await queryHistory({ point_ids: selectedPoints.value.map(point => point.point_id), start_time: apiTime(startDate.value, startHour.value, startMinute.value), end_time: apiTime(endDate.value, endHour.value, endMinute.value), sample_count: sampleCount.value })
    await nextTick(); renderChart()
  } catch (e: any) { error.value = e?.message || '历史数据查询失败' }
  finally { querying.value = false }
}

function renderChart() {
  if (!chartEl.value) return
  chart ||= echarts.init(chartEl.value)
  const series = (result.value?.points || []).map(item => {
    const meta = selectedPoints.value.find(point => point.point_id === item.point_id)
    let values = item.values
    if (mode.value === 'change' && item.values.length) {
      // 每个测点按自身范围归一化到 0～100，消除量纲及绝对数值范围差异。
      const min = Math.min(...item.values)
      const max = Math.max(...item.values)
      const range = max - min
      values = range === 0 ? item.values.map(() => 50) : item.values.map(value => (value - min) / range * 100)
    }
    return {
      name: meta?.point_name || item.point_id,
      type: 'line' as const,
      data: item.times.map((time, index) => [historyTimestamp(time), values[index]]),
      smooth: smooth.value,
      showSymbol: showSymbol.value,
      symbolSize: 5,
      connectNulls: false,
      areaStyle: showArea.value ? { opacity: .08 } : undefined,
      emphasis: { focus: 'series' as const },
    }
  })
  chart.resize()
  chart.setOption({
    animationDuration: 300,
    color: ['#2563eb', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444', '#06b6d4', '#84cc16', '#ec4899', '#6366f1', '#14b8a6'],
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' }, valueFormatter: (value: unknown) => typeof value === 'number' ? `${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}${mode.value === 'change' ? '%' : ''}` : String(value ?? '--') },
    legend: { show: false },
    grid: { left: 62, right: 28, top: 28, bottom: 70 },
    xAxis: { type: 'time', boundaryGap: false, axisLabel: { color: '#64748b' }, splitLine: { show: false } },
    yAxis: { type: 'value', name: mode.value === 'change' ? '归一化趋势（%）' : '数值', min: mode.value === 'change' ? 0 : undefined, max: mode.value === 'change' ? 100 : undefined, nameTextStyle: { color: '#64748b' }, axisLabel: { color: '#64748b', formatter: mode.value === 'change' ? '{value}%' : '{value}' }, splitLine: { lineStyle: { color: '#eef2f7' } }, scale: mode.value !== 'change' },
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 22, bottom: 18 }],
    series,
  }, true)
}

watch([mode, smooth, showSymbol, showArea], renderChart)

onMounted(async () => {
  try { assetTree.value = sortAssetTreeForDisplay(await fetchAssetTree()) }
  catch (e: any) { error.value = e?.message || '资产树加载失败' }
  finally { treeLoading.value = false }
  await nextTick()
  if (chartEl.value) { chart = echarts.init(chartEl.value); resizeObserver = new ResizeObserver(() => chart?.resize()); resizeObserver.observe(chartEl.value); renderChart() }
})
onBeforeUnmount(() => { resizeObserver?.disconnect(); chart?.dispose() })
</script>

<template>
  <main class="page-content">
    <section class="workspace">
      <nav class="sibling-tabs"><button v-for="sib in siblings" :key="sib.route" class="sibling-tab" :class="{ active: route.path === sib.route }" @click="router.push(sib.route)">{{ sib.name }}</button></nav>

      <header class="page-head"><div><h1>历史数据</h1><p>选择测点和时间范围，查询并对比历史变化趋势</p></div></header>
      <div v-if="error" class="message">{{ error }}<button @click="error = ''">×</button></div>

      <div class="content-layout">
        <section class="chart-panel">
          <div class="query-bar">
            <div class="date-time-field">
              <label>开始日期<input v-model="startDate" type="date"></label>
              <div class="time-picker-wrap"><span>开始时间</span><button class="time-display" @click="openTimePicker = openTimePicker === 'start' ? null : 'start'">{{ padTime(startHour) }}:{{ padTime(startMinute) }} <i>▾</i></button>
                <div v-if="openTimePicker === 'start'" class="time-popover"><strong>小时</strong><div class="time-grid hours"><button v-for="hour in hours" :key="hour" :class="{ active: startHour === hour }" @click="startHour = hour">{{ padTime(hour) }}</button></div><strong>分钟</strong><div class="time-grid minutes"><button v-for="minute in startMinutes" :key="minute" :class="{ active: startMinute === minute }" @click="startMinute = minute; openTimePicker = null">{{ padTime(minute) }}</button></div></div>
              </div>
            </div>
            <div class="date-time-field">
              <label>结束日期<input v-model="endDate" type="date"></label>
              <div class="time-picker-wrap"><span>结束时间</span><button class="time-display" @click="openTimePicker = openTimePicker === 'end' ? null : 'end'">{{ padTime(endHour) }}:{{ padTime(endMinute) }} <i>▾</i></button>
                <div v-if="openTimePicker === 'end'" class="time-popover"><strong>小时</strong><div class="time-grid hours"><button v-for="hour in hours" :key="hour" :class="{ active: endHour === hour }" @click="endHour = hour">{{ padTime(hour) }}</button></div><strong>分钟</strong><div class="time-grid minutes end"><button v-for="minute in endMinutes" :key="minute" :class="{ active: endMinute === minute }" @click="endMinute = minute; openTimePicker = null">{{ padTime(minute) }}</button></div></div>
              </div>
            </div>
            <label>每测点采样数<input v-model.number="sampleCount" type="number" min="100" max="1000" step="100"></label>
            <button class="query-btn" :disabled="querying" @click="runQuery">{{ querying ? '查询中...' : '查询数据' }}</button>
          </div>

          <div class="chart-toolbar">
            <div class="segmented"><button :class="{ active: mode === 'value' }" @click="mode = 'value'">原始数值</button><button :class="{ active: mode === 'change' }" title="将每个测点按自身最小值和最大值映射到 0～100%" @click="mode = 'change'">归一化趋势</button></div>
            <label class="check"><input v-model="smooth" type="checkbox"> 平滑曲线</label>
            <label class="check"><input v-model="showSymbol" type="checkbox"> 显示数据点</label>
            <label class="check"><input v-model="showArea" type="checkbox"> 区域填充</label>
            <span v-if="result" class="result-meta">{{ result.timezone }} · {{ result.start_time }} 至 {{ result.actual_end_time }}</span>
          </div>

          <div class="chart-wrap">
            <div ref="chartEl" class="chart"></div>
            <div v-if="!result && !querying" class="chart-empty"><strong>等待查询</strong><p>选择测点并设置时间范围后开始绘制</p></div>
            <div v-if="querying" class="chart-empty"><span class="spinner"></span><strong>正在查询历史数据</strong></div>
          </div>
        </section>

        <aside class="tree-panel">
          <div class="legend-section">
            <div class="legend-head"><div><h2>已选测点</h2><p>{{ selectedPoints.length }} / 10</p></div><button v-if="selectedPoints.length" @click="selectedPoints = []; result = null">清空</button></div>
            <div class="selected-legend"><span v-if="!selectedPoints.length" class="legend-empty">暂未选择测点</span><span v-for="(point, index) in selectedPoints" :key="point.point_id" class="legend-chip"><i :style="{ background: ['#2563eb','#10b981','#f59e0b','#8b5cf6','#ef4444','#06b6d4','#84cc16','#ec4899','#6366f1','#14b8a6'][index] }"></i><span class="legend-content" :title="point.path"><b>{{ point.room_name }} - {{ point.terminal_name }} - {{ point.point_name }}</b><small v-if="pointStats(point.point_id)">{{ pointStats(point.point_id)!.returned_count }} / {{ pointStats(point.point_id)!.original_count }} 条<span v-if="pointStats(point.point_id)!.downsampled"> · 已下采样</span></small><small v-else>尚未查询</small></span><button title="移除" @click="removePoint(point.point_id)">×</button></span></div>
          </div>
          <div class="tree-head"><div><h2>选择测点</h2><p>展开终端后勾选测点</p></div></div>
          <div v-if="treeLoading" class="tree-empty">加载资产树...</div>
          <div v-else class="tree-body">
            <div v-for="building in assetTree" :key="building.asset_id">
              <button class="tree-row level-0" @click="toggle(building.asset_id)"><b :class="{ open: expanded.has(building.asset_id) }">›</b><span>▦</span>{{ building.name }}</button>
              <div v-if="expanded.has(building.asset_id)" class="children">
                <div v-for="floor in building.sub_assets || []" :key="floor.asset_id">
                  <button class="tree-row" @click="toggle(floor.asset_id)"><b :class="{ open: expanded.has(floor.asset_id) }">›</b><span>▤</span>{{ floor.name }}</button>
                  <div v-if="expanded.has(floor.asset_id)" class="children">
                    <div v-for="room in floor.sub_assets || []" :key="room.asset_id">
                      <button class="tree-row" @click="toggle(room.asset_id)"><b :class="{ open: expanded.has(room.asset_id) }">›</b><span>□</span>{{ room.name }}</button>
                      <div v-if="expanded.has(room.asset_id)" class="children">
                        <div v-for="terminal in room.sub_assets || []" :key="terminal.asset_id">
                          <button class="tree-row" @click="toggleTerminal(terminal, `${building.name} / ${floor.name} / ${room.name}`)"><b :class="{ open: expanded.has(terminal.asset_id) }">›</b><span>◇</span>{{ terminal.name }}</button>
                          <div v-if="expanded.has(terminal.asset_id)" class="children">
                            <p v-if="terminalLoading.has(terminal.asset_id)" class="loading-node">加载测点...</p>
                            <template v-else-if="terminalTrees.get(terminal.asset_id)">
                              <div v-for="sensor in terminalTrees.get(terminal.asset_id)!.sensors" :key="sensor.sensor_id" class="sensor-node">
                                <div class="sensor-label"><span>◉</span>{{ sensor.sensor_name }}</div>
                                <label v-for="point in sensor.points" :key="point.point_id" class="point-node" :class="{ selected: pointSelected(point.point_id) }"><input type="checkbox" :checked="pointSelected(point.point_id)" @change="togglePoint(point, sensor.sensor_name, terminalTrees.get(terminal.asset_id)!, room.name, `${building.name} / ${floor.name} / ${room.name} / ${terminal.name} / ${sensor.sensor_name}`)"><span><b>{{ point.point_name }}</b><small>{{ point.point_unit || '无单位' }}</small></span></label>
                              </div>
                              <p v-if="!terminalTrees.get(terminal.asset_id)!.sensors.length" class="loading-node">暂无传感器测点</p>
                            </template>
                          </div>
                        </div>
                        <p v-if="!(room.sub_assets || []).length" class="loading-node">暂无终端</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </section>
  </main>
</template>

<style scoped>
*{box-sizing:border-box}.page-content{flex:1;min-width:0;padding:28px 32px;overflow:hidden;color:#172033}.workspace{height:calc(100vh - 56px);display:flex;flex-direction:column;min-height:0}.sibling-tabs{display:flex;gap:4px;padding:4px;margin-bottom:18px;border-radius:14px;background:#fff;box-shadow:0 4px 16px rgba(15,23,42,.05);flex-shrink:0;overflow-x:auto}.sibling-tab{padding:10px 20px;border:0;border-radius:10px;background:transparent;color:#64748b;font-size:14px;cursor:pointer;white-space:nowrap}.sibling-tab:hover{background:#f1f5f9}.sibling-tab.active{color:#fff;background:#3b82f6}.page-head{margin-bottom:15px;flex-shrink:0}.page-head h1{margin:0 0 5px;font-size:24px}.page-head p{margin:0;color:#8492a6;font-size:13px}.message{display:flex;justify-content:space-between;padding:10px 14px;margin-bottom:12px;border-radius:9px;color:#b91c1c;background:#fef2f2;font-size:13px}.message button{border:0;background:none;color:inherit;cursor:pointer}.content-layout{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:18px;flex:1;min-height:0}.chart-panel,.tree-panel{min-height:0;border:1px solid #e6ebf2;border-radius:14px;background:#fff;box-shadow:0 5px 18px rgba(15,23,42,.045)}.chart-panel{display:flex;flex-direction:column;overflow:visible}.tree-panel{display:flex;flex-direction:column;overflow:hidden}.query-bar{position:relative;z-index:30;display:flex;align-items:end;gap:12px;padding:14px 16px;border-bottom:1px solid #edf1f6}.query-bar label,.time-picker-wrap{display:flex;flex-direction:column;gap:5px;color:#64748b;font-size:11px;font-weight:600}.query-bar input{height:35px;padding:0 9px;border:1px solid #dbe3ee;border-radius:7px;color:#334155;outline:none;background:#fff}.query-bar input[type=date]{width:142px}.query-bar input[type=number]{width:105px}.date-time-field{display:flex;align-items:end;gap:7px}.time-picker-wrap{position:relative}.time-display{width:88px;height:35px;display:flex;align-items:center;justify-content:space-between;padding:0 10px;border:1px solid #dbe3ee;border-radius:7px;color:#334155;background:#fff;cursor:pointer}.time-display i{color:#94a3b8;font-style:normal}.time-popover{position:absolute;top:58px;left:0;width:286px;padding:12px;border:1px solid #dbe3ee;border-radius:10px;background:#fff;box-shadow:0 14px 36px rgba(15,23,42,.2)}.time-popover strong{display:block;margin:0 0 7px;color:#64748b;font-size:11px}.time-popover strong:not(:first-child){margin-top:11px}.time-grid{display:grid;gap:5px}.time-grid.hours{grid-template-columns:repeat(6,1fr)}.time-grid.minutes{grid-template-columns:repeat(4,1fr)}.time-grid.minutes.end{grid-template-columns:repeat(6,1fr)}.time-grid button{height:27px;border:0;border-radius:5px;color:#475569;background:#f1f5f9;font-size:11px;cursor:pointer}.time-grid button:hover{background:#dbeafe}.time-grid button.active{color:#fff;background:#2563eb}.query-btn{height:35px;margin-left:auto;padding:0 20px;border:0;border-radius:7px;color:#fff;background:#2563eb;font-weight:600;cursor:pointer;white-space:nowrap}.query-btn:disabled{opacity:.5}.chart-toolbar{display:flex;align-items:center;gap:14px;padding:10px 16px;border-bottom:1px solid #edf1f6;color:#64748b;font-size:12px;flex-wrap:wrap}.segmented{display:flex;padding:2px;border-radius:7px;background:#eef2f7}.segmented button{padding:5px 10px;border:0;border-radius:5px;background:transparent;color:#64748b;cursor:pointer}.segmented button.active{color:#1d4ed8;background:#fff;box-shadow:0 1px 3px rgba(15,23,42,.1)}.check{display:flex;align-items:center;gap:4px}.result-meta{margin-left:auto;color:#94a3b8}.chart-wrap{position:relative;flex:1;min-height:320px;overflow:hidden}.chart{width:100%;height:100%}.chart-empty{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;background:rgba(255,255,255,.9);color:#94a3b8}.chart-empty strong{margin:7px 0 4px;color:#475569}.chart-empty p{margin:0;font-size:12px}.spinner{width:24px;height:24px;border:3px solid #dbeafe;border-top-color:#2563eb;border-radius:50%;animation:spin .8s linear infinite}.legend-section{max-height:230px;display:flex;flex-direction:column;border-bottom:1px solid #dbe3ee;background:#f8fafc}.legend-head,.tree-head{display:flex;align-items:center;justify-content:space-between;padding:12px 14px}.legend-head h2,.tree-head h2{margin:0 0 2px;font-size:14px}.legend-head p,.tree-head p{margin:0;color:#94a3b8;font-size:10px}.legend-head button{border:0;background:none;color:#dc2626;font-size:11px;cursor:pointer}.selected-legend{display:flex;flex-direction:column;gap:5px;min-height:38px;padding:0 10px 10px;overflow-y:auto}.legend-empty{padding:7px;color:#94a3b8;font-size:11px}.legend-chip{width:100%;display:flex;align-items:center;gap:7px;padding:6px 7px;border:1px solid #e2e8f0;border-radius:6px;color:#475569;background:#fff;font-size:10px}.legend-chip i{width:7px;height:7px;border-radius:50%;flex:none}.legend-content{min-width:0;flex:1;display:flex;flex-direction:column;gap:2px}.legend-content b{overflow:hidden;color:#475569;font-size:10px;font-weight:600;text-overflow:ellipsis;white-space:nowrap}.legend-content small{color:#94a3b8;font-size:9px}.legend-chip button{border:0;background:none;color:#94a3b8;cursor:pointer;font-size:14px}.tree-head{border-bottom:1px solid #e2e8f0}.tree-body{flex:1;padding:8px;overflow:auto}.tree-empty{display:grid;place-items:center;flex:1;color:#94a3b8;font-size:12px}.tree-row{width:100%;height:34px;display:flex;align-items:center;gap:7px;padding:0 7px;border:0;border-radius:6px;background:transparent;color:#475569;text-align:left;cursor:pointer;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.tree-row:hover{background:#f1f5f9}.tree-row.level-0{font-weight:650}.tree-row b{width:10px;color:#94a3b8;font-size:17px;font-weight:400;transition:transform .15s}.tree-row b.open{transform:rotate(90deg)}.children{padding-left:16px}.sensor-node{margin:4px 0}.sensor-label{padding:5px 8px;color:#64748b;font-size:11px;font-weight:600}.point-node{display:flex;align-items:center;gap:7px;margin:2px 0;padding:6px 7px;border-radius:6px;cursor:pointer}.point-node:hover{background:#f1f5f9}.point-node.selected{background:#eff6ff}.point-node input{accent-color:#2563eb}.point-node span{display:flex;justify-content:space-between;gap:8px;min-width:0;flex:1}.point-node b{overflow:hidden;color:#334155;font-size:11px;text-overflow:ellipsis;white-space:nowrap}.point-node small{color:#94a3b8;font-size:9px;white-space:nowrap}.loading-node{margin:5px 8px;color:#94a3b8;font-size:10px}@keyframes spin{to{transform:rotate(360deg)}}@media(max-width:1100px){.query-bar{flex-wrap:wrap}.query-btn{margin-left:0}.content-layout{grid-template-columns:minmax(0,1fr) 285px}.result-meta{display:none}}@media(max-width:760px){.page-content{overflow:auto}.workspace{height:auto}.content-layout{grid-template-columns:1fr}.chart-panel{min-height:650px}.tree-panel{min-height:500px}.date-time-field{width:100%}.query-btn{margin-left:auto}}
</style>
