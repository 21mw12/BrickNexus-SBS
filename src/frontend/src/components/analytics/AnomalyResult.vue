<script setup lang="ts">
import { computed } from 'vue'
import type { AnomalyAnalysisResult, SelectedAnalysisPoint } from '../../api/analytics'
import { buildGapAwareData } from '../../utils/timeSeriesGaps'
import AnalysisChart from './AnalysisChart.vue'
const props = defineProps<{ result: AnomalyAnalysisResult; points: SelectedAnalysisPoint[] }>()
const pointName = (pointId: string) => props.points.find(point => point.point_id === pointId)?.point_name || pointId
const option = computed<any>(() => {
  const series: any[] = []
  for (const group of props.result.series || []) {
    group.point_ids.forEach((pointId: string, column: number) => {
      const values = group.values_by_point?.[column] || group.raw_scores
      const name = pointName(pointId)
      series.push({ name, type: 'line', showSymbol: false, connectNulls: false, data: buildGapAwareData(group.times, values) })
      series.push({ name: `${name}异常`, type: 'scatter', symbolSize: 9, itemStyle: { color: '#ef4444' }, data: group.times.flatMap((time: string, index: number) => group.labels[index] && values[index] != null ? [[time, values[index]]] : []) })
    })
  }
  return { tooltip: { trigger: 'axis' }, legend: { top: 8 }, grid: { left: 55, right: 25, top: 48, bottom: 45 }, xAxis: { type: 'time' }, yAxis: { type: 'value', scale: true }, dataZoom: [{ type: 'inside' }, { type: 'slider' }], series }
})
</script>
<template><div class="anomaly-chart"><AnalysisChart :option="option" /></div></template>
<style scoped>.anomaly-chart{width:100%;height:100%;min-height:330px}</style>
