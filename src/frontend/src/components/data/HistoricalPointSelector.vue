<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { fetchAssetTree, sortAssetTreeForDisplay, type AssetTreeNode } from '../../api/asset'
import { fetchTerminalTree, type PointInfo, type TerminalTree } from '../../api/request'
import type { SelectedAnalysisPoint } from '../../api/analytics'
import { notifyError } from '../../utils/notification'

const props = defineProps<{ modelValue: SelectedAnalysisPoint[] }>()
const emit = defineEmits<{ 'update:modelValue': [value: SelectedAnalysisPoint[]] }>()
const tree = ref<AssetTreeNode[]>([])
const loading = ref(true)
const expanded = reactive(new Set<string>())
const terminalTrees = reactive(new Map<string, TerminalTree>())
const terminalLoading = reactive(new Set<string>())
const selected = (id: string) => props.modelValue.some(item => item.point_id === id)
const toggle = (id: string) => expanded.has(id) ? expanded.delete(id) : expanded.add(id)

async function openTerminal(node: AssetTreeNode) {
  toggle(node.asset_id)
  if (!expanded.has(node.asset_id) || terminalTrees.has(node.asset_id)) return
  terminalLoading.add(node.asset_id)
  try { terminalTrees.set(node.asset_id, await fetchTerminalTree(node.asset_id)) }
  catch (error: any) { notifyError(error?.message || '加载测点失败') }
  finally { terminalLoading.delete(node.asset_id) }
}

function togglePoint(point: PointInfo, sensor: string, terminal: AssetTreeNode, room: AssetTreeNode, path: string) {
  const current = [...props.modelValue]
  const index = current.findIndex(item => item.point_id === point.point_id)
  if (index >= 0) current.splice(index, 1)
  else {
    if (current.length >= 10) { notifyError('一次最多选择10个测点'); return }
    current.push({ ...point, sensor_name: sensor, terminal_name: terminal.name, room_name: room.name, path })
  }
  emit('update:modelValue', current)
}

onMounted(async () => {
  try { tree.value = sortAssetTreeForDisplay(await fetchAssetTree()) }
  catch (error: any) { notifyError(error?.message || '加载资产树失败') }
  finally { loading.value = false }
})
</script>

<template>
  <aside class="selector">
    <header>
      <div><h2>已选测点</h2><p>{{ modelValue.length }} / 10</p></div>
      <button v-if="modelValue.length" @click="$emit('update:modelValue', [])">清空</button>
    </header>
    <div class="selected">
      <span v-if="!modelValue.length">暂未选择测点</span>
      <article v-for="point in modelValue" :key="point.point_id" :title="point.path">
        <b>{{ point.room_name }} - {{ point.point_name }}</b><small>{{ point.point_unit || '无单位' }}</small>
        <button @click="$emit('update:modelValue', modelValue.filter(item => item.point_id !== point.point_id))">×</button>
      </article>
    </div>
    <h3>选择测点</h3>
    <div v-if="loading" class="empty">加载资产树...</div>
    <div v-else class="tree">
      <div v-for="building in tree" :key="building.asset_id">
        <button class="row root" @click="toggle(building.asset_id)">›　▦ {{ building.name }}</button>
        <div v-if="expanded.has(building.asset_id)" class="children">
          <div v-for="floor in building.sub_assets || []" :key="floor.asset_id">
            <button class="row" @click="toggle(floor.asset_id)">›　▤ {{ floor.name }}</button>
            <div v-if="expanded.has(floor.asset_id)" class="children">
              <div v-for="room in floor.sub_assets || []" :key="room.asset_id">
                <button class="row" @click="toggle(room.asset_id)">›　□ {{ room.name }}</button>
                <div v-if="expanded.has(room.asset_id)" class="children">
                  <div v-for="terminal in room.sub_assets || []" :key="terminal.asset_id">
                    <button class="row" @click="openTerminal(terminal)">›　◇ {{ terminal.name }}</button>
                    <div v-if="expanded.has(terminal.asset_id)" class="children">
                      <small v-if="terminalLoading.has(terminal.asset_id)">加载测点...</small>
                      <div v-for="sensor in terminalTrees.get(terminal.asset_id)?.sensors || []" :key="sensor.sensor_id">
                        <strong class="sensor">◉ {{ sensor.sensor_name }}</strong>
                        <label v-for="point in sensor.points" :key="point.point_id" class="point" :class="{ active: selected(point.point_id) }">
                          <input type="checkbox" :checked="selected(point.point_id)" @change="togglePoint(point, sensor.sensor_name, terminal, room, `${building.name} / ${floor.name} / ${room.name} / ${terminal.name} / ${sensor.sensor_name}`)">
                          <span>{{ point.point_name }}</span><small>{{ point.point_unit || '--' }}</small>
                        </label>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
*{box-sizing:border-box}.selector{min-height:0;display:flex;flex-direction:column;border:1px solid #e6ebf2;border-radius:14px;background:#fff;box-shadow:0 5px 18px rgba(15,23,42,.045);overflow:hidden}.selector header{display:flex;justify-content:space-between;padding:12px 14px;background:#f8fafc}.selector h2{margin:0;font-size:14px}.selector p{margin:2px 0 0;color:#94a3b8;font-size:10px}.selector header button,.selected button{border:0;background:none;color:#dc2626;cursor:pointer}.selected{max-height:155px;padding:8px 10px;overflow:auto;color:#94a3b8;font-size:11px;border-bottom:1px solid #e2e8f0}.selected article{display:flex;gap:6px;align-items:center;margin:4px 0;padding:7px;border:1px solid #e2e8f0;border-radius:7px;background:#fff;color:#475569}.selected b{min-width:0;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:10px}.selected small{color:#94a3b8}.selector h3{margin:0;padding:12px 14px;border-bottom:1px solid #e2e8f0;font-size:14px}.tree{flex:1;padding:8px;overflow:auto}.empty{display:grid;place-items:center;flex:1;color:#94a3b8}.row{width:100%;height:34px;border:0;border-radius:6px;background:transparent;color:#475569;text-align:left;cursor:pointer;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.row:hover{background:#f1f5f9}.root{font-weight:650}.children{padding-left:15px}.sensor{display:block;padding:6px;color:#64748b;font-size:11px}.point{display:flex;align-items:center;gap:6px;padding:6px;border-radius:6px;color:#334155;font-size:11px;cursor:pointer}.point:hover,.point.active{background:#eff6ff}.point span{min-width:0;flex:1;overflow:hidden;text-overflow:ellipsis}.point small{color:#94a3b8}.point input{accent-color:#2563eb}
</style>
