<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { HeatmapChart, LineChart } from 'echarts/charts'
import { DataZoomComponent, GridComponent, TooltipComponent, VisualMapComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsType } from 'echarts/core'
import { queryHistoryHeatmap, type HistoryHeatmapResult, type HistoryQueryPayload } from '../../api/history'
import { notifyError } from '../../utils/notification'
import { buildGapAwareData, type GapDisplayMode } from '../../utils/timeSeriesGaps'
import { buildHeatmapDisplayBuckets } from '../../utils/heatmapBuckets'
import DataSectionTabs from '../../components/data/DataSectionTabs.vue'
import HistoricalPointSelector from '../../components/data/HistoricalPointSelector.vue'
import TimeRangeQueryBar, { type TimeRangeValue } from '../../components/data/TimeRangeQueryBar.vue'
import type { SelectedAnalysisPoint } from '../../api/analytics'
import { loadDataPageContext, storeDataPageContext } from '../../utils/dataPageContext'

echarts.use([LineChart, HeatmapChart, GridComponent, TooltipComponent, DataZoomComponent, VisualMapComponent, CanvasRenderer])

const savedContext = loadDataPageContext()
const selectedPoints = ref<SelectedAnalysisPoint[]>(savedContext?.points || [])
const heatmapResult = ref<HistoryHeatmapResult | null>(null)
const hasQueried = ref(false)
const querying = ref(false)
const error = ref('')
watch(error, value => { if (value) { notifyError(value, '历史数据错误'); error.value = '' } })
const chartEl = ref<HTMLDivElement | null>(null)
let chart: EChartsType | null = null
let resizeObserver: ResizeObserver | null = null

const mode = ref<'value' | 'change'>('value')
const chartType = ref<'line' | 'time-heatmap' | 'correlation'>('line')
const correlationMethod = ref<'pearson' | 'spearman'>('pearson')
const heatmapColorScale = ref<'per-point' | 'global'>('per-point')
const smooth = ref(true)
const showSymbol = ref(false)
const showArea = ref(false)
const gapDisplayMode = ref<GapDisplayMode>('auto')
const padTime = (value: number) => String(value).padStart(2, '0')
const formatTimeValue = (date: Date) => `${date.getFullYear()}-${padTime(date.getMonth()+1)}-${padTime(date.getDate())} ${padTime(date.getHours())}:${padTime(date.getMinutes())}:00`
const roundedEnd = new Date()
roundedEnd.setMinutes(Math.floor(roundedEnd.getMinutes() / 15) * 15, 0, 0)
const roundedStart = new Date(roundedEnd.getTime() - 24 * 60 * 60 * 1000)
const range = ref<TimeRangeValue>(savedContext?.range || { start_time: formatTimeValue(roundedStart), end_time: formatTimeValue(roundedEnd), sample_count: 500 })
const currentResult = computed(() => heatmapResult.value)
const heatmapDisplay = computed(() => heatmapResult.value ? buildHeatmapDisplayBuckets(
  heatmapResult.value.times,
  heatmapResult.value.points.map(point => point.values),
  heatmapResult.value.actual_end_time,
) : null)

function invalidateResults() {
  heatmapResult.value = null
  hasQueried.value = false
  chart?.clear()
}

function historyTimestamp(value: string) {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})$/)
  if (!match) return Date.parse(value.replace(' ', 'T'))
  const [, year, month, day, hour, minute, second] = match
  return new Date(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute), Number(second)).getTime()
}

function validateQuery() {
  if (!selectedPoints.value.length) return '请至少选择一个测点'
  if (chartType.value === 'correlation' && selectedPoints.value.length < 2) return '相关性分析至少需要选择两个测点'
  const start = new Date(range.value.start_time.replace(' ', 'T'))
  const end = new Date(range.value.end_time.replace(' ', 'T'))
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return '请选择有效的开始和结束时间'
  if (end <= start) return '结束时间必须晚于开始时间'
  const duration = end.getTime() - start.getTime()
  if (duration < 15 * 60 * 1000) return '查询范围不能少于 15 分钟'
  if (duration > 31 * 24 * 60 * 60 * 1000) return '查询范围不能超过 31 天'
  if (!Number.isInteger(range.value.sample_count) || range.value.sample_count < 100 || range.value.sample_count > 1000) return '采样数量必须为 100～1000 的整数'
  return ''
}

function queryPayload(): HistoryQueryPayload {
  return { point_ids: selectedPoints.value.map(point => point.point_id), ...range.value }
}

async function loadCurrentChart(force = false) {
  error.value = validateQuery()
  if (error.value) return
  querying.value = true
  try {
    if (force || !heatmapResult.value) {
      heatmapResult.value = await queryHistoryHeatmap(queryPayload())
    }
    hasQueried.value = true
    await nextTick(); renderChart()
  } catch (e: any) { error.value = e?.message || '历史数据查询失败' }
  finally { querying.value = false }
}

async function runQuery() { await loadCurrentChart(true) }

function pointLabel(pointId: string) {
  return selectedPoints.value.find(point => point.point_id === pointId)?.point_name || pointId
}

function pointUnit(pointId: string) {
  return selectedPoints.value.find(point => point.point_id === pointId)?.point_unit || ''
}

function renderChart() {
  if (!chartEl.value) return
  chart ||= echarts.init(chartEl.value)
  if (chartType.value === 'time-heatmap') { renderTimeHeatmap(); return }
  if (chartType.value === 'correlation') { renderCorrelationHeatmap(); return }
  const source = heatmapResult.value
  const series = (source?.points || []).map(item => {
    const meta = selectedPoints.value.find(point => point.point_id === item.point_id)
    const values = mode.value === 'change' ? item.normalized_values : item.values
    return {
      name: meta?.point_name || item.point_id,
      type: 'line' as const,
      data: buildGapAwareData((source?.times || []).map(historyTimestamp), values, gapDisplayMode.value),
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

function renderTimeHeatmap() {
  if (!chart || !heatmapResult.value || !heatmapDisplay.value) { chart?.clear(); return }
  const source = heatmapResult.value
  const display = heatmapDisplay.value
  const pointIds = source.points.map(point => point.point_id)
  const missingData: any[] = []
  const data: any[] = []
  source.points.forEach((_point, pointIndex) => {
    const rawValues = display.values[pointIndex] || []
    const displayValues = mode.value === 'change' ? display.normalizedValues[pointIndex] || [] : rawValues
    const colorValues = heatmapColorScale.value === 'per-point' ? display.normalizedValues[pointIndex] || [] : displayValues
    displayValues.forEach((displayValue, timeIndex) => {
      const colorValue = colorValues[timeIndex]
      if (displayValue == null || colorValue == null) missingData.push([timeIndex, pointIndex, 0, null])
      else data.push([timeIndex, pointIndex, colorValue, displayValue, rawValues[timeIndex]])
    })
  })
  chart.resize()
  chart.setOption({
    animationDuration: 250,
    tooltip: { position: 'top', formatter: (params: any) => {
      const [timeIndex, pointIndex, , displayValue, rawValue] = params.value
      const pointId = pointIds[pointIndex] || ''
      const shown = rawValue == null ? '--' : Number(displayValue).toLocaleString(undefined, { maximumFractionDigits: 2 }) + (mode.value === 'change' ? '%' : pointUnit(pointId))
      const timeRange = `${display.startTimes[timeIndex]} 至 ${display.endTimes[timeIndex]}`
      return `<b>${pointLabel(pointId)}</b><br/>${timeRange}<br/>显示值：${shown}<br/>桶内平均值：${rawValue == null ? '--' : Number(rawValue).toLocaleString(undefined, { maximumFractionDigits: 3 }) + pointUnit(pointId)}`
    } },
    grid: { left: 125, right: 38, top: 55, bottom: 78 },
    xAxis: { type: 'category', data: display.startTimes, name: '时间', axisLabel: { color: '#64748b', formatter: (value: string) => value.slice(5, 16) }, splitArea: { show: false } },
    yAxis: { type: 'category', data: pointIds.map(pointLabel), name: '测点', axisLabel: { color: '#475569', width: 105, overflow: 'truncate' } },
    visualMap: [
      { min: 0, max: 1, dimension: 2, seriesIndex: 0, show: false, inRange: { color: ['#e2e8f0', '#e2e8f0'] } },
      { min: heatmapColorScale.value === 'per-point' || mode.value === 'change' ? 0 : source.value_range.min, max: heatmapColorScale.value === 'per-point' || mode.value === 'change' ? 100 : source.value_range.max, dimension: 2, seriesIndex: 1, calculable: true, orient: 'horizontal', left: 'center', top: 8, text: heatmapColorScale.value === 'per-point' || mode.value === 'change' ? ['相对高', '相对低'] : ['高', '低'], inRange: { color: ['#eff6ff', '#93c5fd', '#2563eb', '#1e3a8a'] } },
    ],
    dataZoom: [{ type: 'inside', xAxisIndex: 0 }, { type: 'slider', xAxisIndex: 0, height: 22, bottom: 18 }],
    series: [
      { name: '缺失数据', type: 'heatmap', data: missingData, silent: false, itemStyle: { color: '#e2e8f0', borderWidth: 0 } },
      { name: '测量数据', type: 'heatmap', data, progressive: 3000, itemStyle: { borderWidth: 0 }, emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(15,23,42,.28)' } } },
    ],
  }, true)
}

function renderCorrelationHeatmap() {
  if (!chart || !heatmapResult.value || selectedPoints.value.length < 2) { chart?.clear(); return }
  const source = heatmapResult.value
  const pointIds = source.points.map(point => point.point_id)
  const matrix = source.correlations[correlationMethod.value]
  const missingData: any[] = []
  const data: any[] = []
  matrix.forEach((row, rowIndex) => row.forEach((value, columnIndex) => {
    const item = [columnIndex, rowIndex, value ?? 0, source.correlations.pair_counts[rowIndex]?.[columnIndex] ?? 0]
    if (value == null) missingData.push(item)
    else data.push(item)
  }))
  chart.resize()
  chart.setOption({
    animationDuration: 250,
    tooltip: { position: 'top', formatter: (params: any) => {
      const [column, row, value, count] = params.value
      return `<b>${pointLabel(pointIds[row] || '')} × ${pointLabel(pointIds[column] || '')}</b><br/>算法：${correlationMethod.value === 'pearson' ? 'Pearson' : 'Spearman'}<br/>相关系数：${params.seriesName === '缺失数据' ? '--' : Number(value).toFixed(4)}<br/>有效时间桶：${count}`
    } },
    grid: { left: 125, right: 45, top: 65, bottom: 100 },
    xAxis: { type: 'category', data: pointIds.map(pointLabel), axisLabel: { color: '#475569', rotate: 30, width: 100, overflow: 'truncate' } },
    yAxis: { type: 'category', data: pointIds.map(pointLabel), axisLabel: { color: '#475569', width: 105, overflow: 'truncate' } },
    visualMap: [
      { min: 0, max: 1, dimension: 2, seriesIndex: 0, show: false, inRange: { color: ['#e2e8f0', '#e2e8f0'] } },
      { min: -1, max: 1, dimension: 2, seriesIndex: 1, calculable: false, orient: 'horizontal', left: 'center', top: 12, text: ['正相关', '负相关'], inRange: { color: ['#2563eb', '#dbeafe', '#ffffff', '#fee2e2', '#dc2626'] } },
    ],
    series: [
      { name: '缺失数据', type: 'heatmap', data: missingData, itemStyle: { color: '#e2e8f0', borderWidth: 0 }, label: { show: true, color: '#64748b', formatter: '--' } },
      { name: '相关系数', type: 'heatmap', data, itemStyle: { borderWidth: 0 }, label: { show: true, color: '#334155', formatter: (params: any) => Number(params.value[2]).toFixed(2) }, emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(15,23,42,.28)' } } },
    ],
  }, true)
}

watch([mode, smooth, showSymbol, showArea, gapDisplayMode, correlationMethod, heatmapColorScale], renderChart)
watch(chartType, async () => {
  if (hasQueried.value) await loadCurrentChart(false)
  else renderChart()
})
watch([selectedPoints, range], invalidateResults, { deep: true })
watch([selectedPoints, range], () => storeDataPageContext(range.value, selectedPoints.value), { deep: true })

onMounted(async () => {
  await nextTick()
  if (chartEl.value) { chart = echarts.init(chartEl.value); resizeObserver = new ResizeObserver(() => chart?.resize()); resizeObserver.observe(chartEl.value); renderChart() }
})
onBeforeUnmount(() => { resizeObserver?.disconnect(); chart?.dispose() })
</script>

<template>
  <main class="page-content">
    <section class="workspace">
      <DataSectionTabs />

      <header class="page-head"><div><h1>历史数据</h1><p>选择测点和时间范围，查询并对比历史变化趋势</p></div></header>
      <div class="content-layout">
        <section class="chart-panel">
          <TimeRangeQueryBar v-model="range" :busy="querying" action-label="查询数据" @submit="runQuery" />

          <div class="chart-toolbar">
            <div class="segmented" :class="{ disabled: chartType === 'correlation' }"><button :disabled="chartType === 'correlation'" :class="{ active: mode === 'value' }" @click="mode = 'value'">原始数值</button><button :disabled="chartType === 'correlation'" :class="{ active: mode === 'change' }" title="由后端将每个测点按自身最小值和最大值映射到 0～100%" @click="mode = 'change'">归一化趋势</button></div>
            <template v-if="chartType === 'line'">
              <label class="check"><input v-model="smooth" type="checkbox"> 平滑曲线</label>
              <label class="check"><input v-model="showSymbol" type="checkbox"> 显示数据点</label>
              <label class="check"><input v-model="showArea" type="checkbox"> 区域填充</label>
              <label class="toolbar-select">断线规则<select v-model="gapDisplayMode"><option value="auto">按采样节奏自动判断</option><option value="strict">空桶即断开</option><option value="connect">始终连接</option></select></label>
              <span v-if="gapDisplayMode==='auto'" class="mode-hint">超过典型采样间隔约3倍时断开</span>
            </template>
            <label v-if="chartType === 'time-heatmap'" class="toolbar-select">颜色范围<select v-model="heatmapColorScale"><option value="per-point">按测点独立</option><option value="global">所有测点统一</option></select></label>
            <span v-if="chartType === 'time-heatmap' && heatmapDisplay" class="mode-hint">{{ range.sample_count }} 个计算桶合并为 {{ heatmapDisplay.startTimes.length }} 个显示桶，桶内取平均</span>
            <label v-if="chartType === 'correlation'" class="toolbar-select">相关性算法<select v-model="correlationMethod"><option value="pearson">Pearson</option><option value="spearman">Spearman</option></select></label>
            <span v-if="chartType === 'correlation'" class="mode-hint">相关性不受数值模式影响</span>
            <label class="toolbar-select chart-type-select">图表类型<select v-model="chartType"><option value="line">折线图</option><option value="time-heatmap">时间热力图</option><option value="correlation">相关性热力图</option></select></label>
          </div>

          <div class="chart-wrap">
            <div ref="chartEl" class="chart"></div>
            <div v-if="chartType === 'correlation' && selectedPoints.length < 2 && !querying" class="chart-empty"><strong>请选择至少两个测点</strong><p>相关性热力图用于对照不同测点之间的相关关系</p></div>
            <div v-else-if="!currentResult && !querying" class="chart-empty"><strong>等待查询</strong><p>选择测点并设置时间范围后开始绘制</p></div>
            <div v-if="querying" class="chart-empty"><span class="spinner"></span><strong>正在查询历史数据</strong></div>
          </div>
        </section>

        <HistoricalPointSelector v-model="selectedPoints" />
      </div>
    </section>
  </main>
</template>

<style scoped>
*{box-sizing:border-box}.page-content{flex:1;min-width:0;padding:28px 32px;overflow:hidden;color:#172033}.workspace{height:calc(100vh - 56px);display:flex;flex-direction:column;min-height:0}.sibling-tabs{display:flex;gap:4px;padding:4px;margin-bottom:18px;border-radius:14px;background:#fff;box-shadow:0 4px 16px rgba(15,23,42,.05);flex-shrink:0;overflow-x:auto}.sibling-tab{padding:10px 20px;border:0;border-radius:10px;background:transparent;color:#64748b;font-size:14px;cursor:pointer;white-space:nowrap}.sibling-tab:hover{background:#f1f5f9}.sibling-tab.active{color:#fff;background:#3b82f6}.page-head{margin-bottom:15px;flex-shrink:0}.page-head h1{margin:0 0 5px;font-size:24px}.page-head p{margin:0;color:#8492a6;font-size:13px}.message{display:flex;justify-content:space-between;padding:10px 14px;margin-bottom:12px;border-radius:9px;color:#b91c1c;background:#fef2f2;font-size:13px}.message button{border:0;background:none;color:inherit;cursor:pointer}.content-layout{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:18px;flex:1;min-height:0}.chart-panel,.tree-panel{min-height:0;border:1px solid #e6ebf2;border-radius:14px;background:#fff;box-shadow:0 5px 18px rgba(15,23,42,.045)}.chart-panel{display:flex;flex-direction:column;overflow:visible}.tree-panel{display:flex;flex-direction:column;overflow:hidden}.query-bar{position:relative;z-index:30;display:flex;align-items:end;gap:12px;padding:14px 16px;border-bottom:1px solid #edf1f6}.query-bar label,.time-picker-wrap{display:flex;flex-direction:column;gap:5px;color:#64748b;font-size:11px;font-weight:600}.query-bar input{height:35px;padding:0 9px;border:1px solid #dbe3ee;border-radius:7px;color:#334155;outline:none;background:#fff}.query-bar input[type=date]{width:142px}.query-bar input[type=number]{width:105px}.date-time-field{display:flex;align-items:end;gap:7px}.time-picker-wrap{position:relative}.time-display{width:88px;height:35px;display:flex;align-items:center;justify-content:space-between;padding:0 10px;border:1px solid #dbe3ee;border-radius:7px;color:#334155;background:#fff;cursor:pointer}.time-display i{color:#94a3b8;font-style:normal}.time-popover{position:absolute;top:58px;left:0;width:286px;padding:12px;border:1px solid #dbe3ee;border-radius:10px;background:#fff;box-shadow:0 14px 36px rgba(15,23,42,.2)}.time-popover strong{display:block;margin:0 0 7px;color:#64748b;font-size:11px}.time-popover strong:not(:first-child){margin-top:11px}.time-grid{display:grid;gap:5px}.time-grid.hours{grid-template-columns:repeat(6,1fr)}.time-grid.minutes{grid-template-columns:repeat(4,1fr)}.time-grid.minutes.end{grid-template-columns:repeat(6,1fr)}.time-grid button{height:27px;border:0;border-radius:5px;color:#475569;background:#f1f5f9;font-size:11px;cursor:pointer}.time-grid button:hover{background:#dbeafe}.time-grid button.active{color:#fff;background:#2563eb}.query-btn{height:35px;margin-left:auto;padding:0 20px;border:0;border-radius:7px;color:#fff;background:#2563eb;font-weight:600;cursor:pointer;white-space:nowrap}.query-btn:disabled{opacity:.5}.chart-toolbar{display:flex;align-items:center;gap:14px;padding:10px 16px;border-bottom:1px solid #edf1f6;color:#64748b;font-size:12px;flex-wrap:wrap}.segmented{display:flex;padding:2px;border-radius:7px;background:#eef2f7}.segmented button{padding:5px 10px;border:0;border-radius:5px;background:transparent;color:#64748b;cursor:pointer}.segmented button.active{color:#1d4ed8;background:#fff;box-shadow:0 1px 3px rgba(15,23,42,.1)}.check{display:flex;align-items:center;gap:4px}.result-meta{margin-left:auto;color:#94a3b8}.chart-wrap{position:relative;flex:1;min-height:320px;overflow:hidden}.chart{width:100%;height:100%}.chart-empty{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;background:rgba(255,255,255,.9);color:#94a3b8}.chart-empty strong{margin:7px 0 4px;color:#475569}.chart-empty p{margin:0;font-size:12px}.spinner{width:24px;height:24px;border:3px solid #dbeafe;border-top-color:#2563eb;border-radius:50%;animation:spin .8s linear infinite}.legend-section{max-height:230px;display:flex;flex-direction:column;border-bottom:1px solid #dbe3ee;background:#f8fafc}.legend-head,.tree-head{display:flex;align-items:center;justify-content:space-between;padding:12px 14px}.legend-head h2,.tree-head h2{margin:0 0 2px;font-size:14px}.legend-head p,.tree-head p{margin:0;color:#94a3b8;font-size:10px}.legend-head button{border:0;background:none;color:#dc2626;font-size:11px;cursor:pointer}.selected-legend{display:flex;flex-direction:column;gap:5px;min-height:38px;padding:0 10px 10px;overflow-y:auto}.legend-empty{padding:7px;color:#94a3b8;font-size:11px}.legend-chip{width:100%;display:flex;align-items:center;gap:7px;padding:6px 7px;border:1px solid #e2e8f0;border-radius:6px;color:#475569;background:#fff;font-size:10px}.legend-chip i{width:7px;height:7px;border-radius:50%;flex:none}.legend-content{min-width:0;flex:1;display:flex;flex-direction:column;gap:2px}.legend-content b{overflow:hidden;color:#475569;font-size:10px;font-weight:600;text-overflow:ellipsis;white-space:nowrap}.legend-content small{color:#94a3b8;font-size:9px}.legend-chip button{border:0;background:none;color:#94a3b8;cursor:pointer;font-size:14px}.tree-head{border-bottom:1px solid #e2e8f0}.tree-body{flex:1;padding:8px;overflow:auto}.tree-empty{display:grid;place-items:center;flex:1;color:#94a3b8;font-size:12px}.tree-row{width:100%;height:34px;display:flex;align-items:center;gap:7px;padding:0 7px;border:0;border-radius:6px;background:transparent;color:#475569;text-align:left;cursor:pointer;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.tree-row:hover{background:#f1f5f9}.tree-row.level-0{font-weight:650}.tree-row b{width:10px;color:#94a3b8;font-size:17px;font-weight:400;transition:transform .15s}.tree-row b.open{transform:rotate(90deg)}.children{padding-left:16px}.sensor-node{margin:4px 0}.sensor-label{padding:5px 8px;color:#64748b;font-size:11px;font-weight:600}.point-node{display:flex;align-items:center;gap:7px;margin:2px 0;padding:6px 7px;border-radius:6px;cursor:pointer}.point-node:hover{background:#f1f5f9}.point-node.selected{background:#eff6ff}.point-node input{accent-color:#2563eb}.point-node span{display:flex;justify-content:space-between;gap:8px;min-width:0;flex:1}.point-node b{overflow:hidden;color:#334155;font-size:11px;text-overflow:ellipsis;white-space:nowrap}.point-node small{color:#94a3b8;font-size:9px;white-space:nowrap}.loading-node{margin:5px 8px;color:#94a3b8;font-size:10px}@keyframes spin{to{transform:rotate(360deg)}}@media(max-width:1100px){.query-bar{flex-wrap:wrap}.query-btn{margin-left:0}.content-layout{grid-template-columns:minmax(0,1fr) 285px}.result-meta{display:none}}@media(max-width:760px){.page-content{overflow:auto}.workspace{height:auto}.content-layout{grid-template-columns:1fr}.chart-panel{min-height:650px}.tree-panel{min-height:500px}.date-time-field{width:100%}.query-btn{margin-left:auto}}
.segmented.disabled{opacity:.55}.segmented button:disabled{cursor:not-allowed}.toolbar-select{display:flex;align-items:center;gap:6px;color:#64748b;font-size:11px;font-weight:600;white-space:nowrap}.toolbar-select select{height:30px;padding:0 28px 0 9px;border:1px solid #dbe3ee;border-radius:7px;color:#334155;background:#fff;outline:none}.toolbar-select select:focus{border-color:#60a5fa;box-shadow:0 0 0 3px rgba(59,130,246,.12)}.mode-hint{color:#94a3b8;font-size:11px}.result-meta{margin-left:0}.chart-type-select{margin-left:auto}@media(max-width:760px){.chart-type-select{margin-left:0}}
</style>
