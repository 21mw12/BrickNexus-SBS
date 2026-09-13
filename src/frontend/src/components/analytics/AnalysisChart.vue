<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
const props=defineProps<{option:echarts.EChartsOption}>()
const el=ref<HTMLDivElement|null>(null);let chart:echarts.ECharts|null=null,observer:ResizeObserver|null=null
function draw(){if(!el.value)return;chart||=echarts.init(el.value);chart.setOption(props.option,true)}
watch(()=>props.option,()=>nextTick(draw),{deep:true});onMounted(()=>{draw();observer=new ResizeObserver(()=>chart?.resize());if(el.value)observer.observe(el.value)});onBeforeUnmount(()=>{observer?.disconnect();chart?.dispose()})
</script>
<template><div ref="el" class="analysis-chart"></div></template>
<style scoped>.analysis-chart{width:100%;height:100%;min-height:330px}</style>
