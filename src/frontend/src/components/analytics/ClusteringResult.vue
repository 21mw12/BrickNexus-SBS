<script setup lang="ts">
import { computed } from 'vue'
import type { ClusteringAnalysisResult, SelectedAnalysisPoint } from '../../api/analytics'
import AnalysisChart from './AnalysisChart.vue'
const props=defineProps<{result:ClusteringAnalysisResult;points:SelectedAnalysisPoint[]}>()
const colors=['#2563eb','#10b981','#f59e0b','#8b5cf6','#ef4444','#06b6d4','#84cc16','#ec4899']
const option=computed<any>(()=>{
  const count=props.result.cluster_count||0
  const states=Array.from({length:count},(_,index)=>`状态 ${index+1}`)
  const pcaSeries=states.map((name,cluster)=>({name,type:'scatter',xAxisIndex:0,yAxisIndex:0,symbolSize:8,itemStyle:{color:colors[cluster]},data:(props.result.pca?.coordinates||[]).flatMap((item:number[],index:number)=>props.result.labels[index]===cluster?[item]:[])}))
  const timelineSeries=states.map((name,cluster)=>({name:`${name} 时间`,type:'scatter',xAxisIndex:1,yAxisIndex:1,symbol:'rect',symbolSize:[8,10],itemStyle:{color:colors[cluster]},data:(props.result.times||[]).flatMap((time:string,index:number)=>props.result.labels[index]===cluster?[[time,name]]:[])}))
  return {tooltip:{trigger:'item'},legend:{top:8},grid:[{left:55,right:25,top:48,height:'48%'},{left:75,right:25,top:'72%',bottom:35}],xAxis:[{type:'value',name:'PCA 第一主成分',gridIndex:0},{type:'time',name:'时间',gridIndex:1}],yAxis:[{type:'value',name:'PCA 第二主成分',gridIndex:0},{type:'category',data:states,name:'运行状态',gridIndex:1}],series:[...pcaSeries,...timelineSeries]}
})
</script>
<template><div class="cluster-chart"><AnalysisChart :option="option"/></div></template>
<style scoped>.cluster-chart{width:100%;height:100%;min-height:430px}.cluster-chart :deep(.analysis-chart){min-height:430px}</style>
