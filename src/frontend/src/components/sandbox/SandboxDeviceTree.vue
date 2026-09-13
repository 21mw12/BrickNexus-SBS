<script setup lang="ts">
import type { SandboxConfig } from '../../api/sandbox'

defineProps<{
  config: SandboxConfig
  selectedPointIds: string[]
  activePointId: string
}>()
const emit = defineEmits<{
  toggle: [pointId: string]
  activate: [pointId: string]
  clear: []
}>()
</script>

<template>
  <aside class="device-panel">
    <header>
      <div><span>ROOM TOPOLOGY</span><h2>虚拟设备</h2></div>
      <div class="selection-count"><b>{{selectedPointIds.length}} / 10</b><button v-if="selectedPointIds.length" @click="emit('clear')">清空</button></div>
    </header>
    <div class="tree">
      <section v-for="(terminal,ti) in config.terminals" :key="`${terminal.name}-${ti}`" class="terminal">
        <div class="terminal-title"><i>▣</i><b>{{terminal.name}}</b></div>
        <div v-for="(sensor,si) in terminal.sensors" :key="`${sensor.name}-${si}`" class="sensor">
          <div class="sensor-title"><i></i><span>{{sensor.name}}</span><small>{{sensor.points.length}}</small></div>
          <div v-for="point in sensor.points" :key="point.id" class="point-row" :class="{active:activePointId===point.id,selected:selectedPointIds.includes(point.id)}">
            <label :title="selectedPointIds.includes(point.id)?'从图表移除':'添加到图表'">
              <input type="checkbox" :checked="selectedPointIds.includes(point.id)" @change="emit('toggle',point.id)">
              <i></i>
            </label>
            <button @click="emit('activate',point.id)"><span>{{point.name}}</span><small>{{point.unit||'—'}}</small></button>
          </div>
        </div>
      </section>
    </div>
  </aside>
</template>

<style scoped>
*{box-sizing:border-box}.device-panel{min-height:0;display:flex;flex-direction:column;overflow:hidden;border:1px solid #e6ebf2;border-radius:16px;background:#fff;box-shadow:0 5px 18px rgba(15,23,42,.045)}header{min-height:67px;display:flex;align-items:center;justify-content:space-between;padding:13px 16px;border-bottom:1px solid #edf1f6;background:linear-gradient(135deg,#fbfdff,#fff)}header span{display:block;margin-bottom:3px;color:#3b82f6;font-size:8px;font-weight:800;letter-spacing:.12em}h2{margin:0;color:#172033;font-size:15px}.selection-count{display:flex;align-items:flex-end;flex-direction:column;gap:3px}.selection-count b{padding:4px 7px;border-radius:8px;color:#2563eb;background:#eff6ff;font-size:9px}.selection-count button{padding:0;border:0;color:#94a3b8;background:none;font-size:8px;cursor:pointer}.tree{flex:1;min-height:0;padding:12px 10px;overflow:auto}.terminal{margin-bottom:13px}.terminal-title{display:flex;align-items:center;gap:7px;padding:6px 7px;color:#334155;font-size:12px}.terminal-title i{color:#3b82f6;font-style:normal}.sensor{margin-left:11px;padding-left:11px;border-left:1px solid #dbe3ee}.sensor-title{height:31px;display:flex;align-items:center;gap:7px;color:#64748b;font-size:10px}.sensor-title>i{width:7px;height:7px;border:2px solid #60a5fa;border-radius:50%;background:#fff}.sensor-title span{min-width:0;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.sensor-title small{padding:2px 5px;border-radius:6px;background:#f1f5f9}.point-row{height:35px;display:flex;align-items:center;border-radius:7px;color:#64748b}.point-row:hover{background:#f8fafc}.point-row.active{box-shadow:inset 2px 0 #3b82f6;background:#f8fbff}.point-row.selected{color:#1d4ed8;background:#eff6ff}.point-row>label{position:relative;width:28px;height:100%;display:grid;place-items:center;cursor:pointer}.point-row input{position:absolute;opacity:0}.point-row label i{width:13px;height:13px;border:1px solid #cbd5e1;border-radius:4px;background:#fff}.point-row input:checked+i{border-color:#3b82f6;background:#3b82f6;box-shadow:inset 0 0 0 3px #fff}.point-row>button{min-width:0;height:100%;display:flex;align-items:center;justify-content:space-between;flex:1;padding:0 8px 0 2px;border:0;color:inherit;background:transparent;cursor:pointer}.point-row button span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:11px}.point-row button small{color:#94a3b8;font-size:9px}
</style>
