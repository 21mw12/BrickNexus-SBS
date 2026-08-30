<script setup lang="ts">
import { computed, defineComponent, h, onBeforeUnmount, onMounted, reactive, ref, type PropType } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchAssetTree, sortAssetTreeForDisplay, type AssetTreeNode } from '../../api/asset'
import { fetchFloorPlan, fetchFloorPlanImage, type FloorPlan, type FloorRoomRegion } from '../../api/floorPlan'
import { fetchTerminalTree, type TerminalTree } from '../../api/request'
import {
  TerminalRealtimeSocket, type RealtimeConnectionState, type RealtimeErrorMessage,
  type RealtimeMessage, type SnapshotMessage, type TerminalSnapshot,
} from '../../api/realtime'
import { isMenuGroup, menuConfig } from '../../config/menu'
import { redirectToLogin } from '../../utils/authSession'
import ControlExecutionModal from '../modals/ControlExecutionModal.vue'
import type { ControlAssetType } from '../../api/control'

type Selection = { type: 'floor' | 'room'; node: AssetTreeNode; floor: AssetTreeNode; building: AssetTreeNode }

const route = useRoute()
const router = useRouter()
const siblings = computed(() => {
  for (const entry of menuConfig) if (isMenuGroup(entry) && entry.children.some(item => item.route === route.path)) return entry.children
  return []
})

const tree = ref<AssetTreeNode[]>([])
const treeLoading = ref(true)
const expandedBuildings = reactive(new Set<string>())
const expandedFloors = reactive(new Set<string>())
const selection = ref<Selection | null>(null)
const connectionState = ref<RealtimeConnectionState>('idle')
const snapshots = reactive(new Map<string, TerminalSnapshot>())
const metadata = reactive(new Map<string, TerminalTree>())
const metadataLoading = reactive(new Set<string>())
const missingIds = ref<string[]>([])
const rejectedIds = ref<string[]>([])
const errorMessage = ref('')
const infoMessage = ref('')
const floorPlan = ref<FloorPlan | null>(null)
const floorImageUrl = ref('')
const planLoading = ref(false)
const controlTarget = ref<{ id: string; type: ControlAssetType; name: string } | null>(null)
let selectionVersion = 0

const socket = new TerminalRealtimeSocket({
  onState: state => { connectionState.value = state },
  onMessage: handleRealtimeMessage,
})

const selectedRooms = computed(() => {
  const current = selection.value
  if (!current) return []
  return current.type === 'room' ? [current.node] : (current.floor.sub_assets || [])
})
const selectedTerminalNodes = computed(() => selectedRooms.value.flatMap(room => room.sub_assets || []))
const selectedTerminalIds = computed(() => selectedTerminalNodes.value.map(item => item.asset_id))
const selectedTitle = computed(() => selection.value ? `${selection.value.building.name} / ${selection.value.floor.name}${selection.value.type === 'room' ? ` / ${selection.value.node.name}` : ''}` : '尚未选择监控范围')
const onlineCount = computed(() => selectedTerminalIds.value.filter(id => snapshots.get(id)?.terminal_status === true).length)
const offlineCount = computed(() => selectedTerminalIds.value.filter(id => snapshots.get(id)?.terminal_status === false).length)
const latestTime = computed(() => {
  const times = selectedTerminalIds.value.map(id => snapshots.get(id)?.time).filter((item): item is string => !!item)
  return times.sort((a, b) => Date.parse(b) - Date.parse(a))[0] || ''
})
const unmarkedRooms = computed(() => {
  if (!floorPlan.value) return []
  const marked = new Set(floorPlan.value.regions.map(region => region.room_id))
  return selectedRooms.value.filter(room => !marked.has(room.asset_id))
})
const connectionText = computed(() => ({
  idle: '等待选择', connecting: '连接中', connected: '已连接', reconnecting: '重连中', unauthorized: '无权限', closed: '已关闭',
}[connectionState.value]))

function handleRealtimeMessage(message: RealtimeMessage) {
  if (message.type === 'snapshot') return applySnapshot(message)
  if (message.type === 'terminal_update') {
    if (selectedTerminalIds.value.includes(message.terminal_id)) snapshots.set(message.terminal_id, message.data)
    missingIds.value = missingIds.value.filter(id => id !== message.terminal_id)
    return
  }
  applySocketError(message)
}

function applySnapshot(message: SnapshotMessage) {
  snapshots.clear()
  for (const item of message.data) snapshots.set(item.terminal_id, item)
  missingIds.value = message.missing_terminal_ids
  rejectedIds.value = message.rejected_terminal_ids
  infoMessage.value = message.missing_terminal_ids.length ? `${message.missing_terminal_ids.length} 个终端正在等待首次数据` : ''
  if (message.rejected_terminal_ids.length) errorMessage.value = `${message.rejected_terminal_ids.length} 个终端无权访问或资产不可用`
}

function applySocketError(message: RealtimeErrorMessage) {
  const labels: Record<string, string> = {
    invalid_message: '实时服务消息格式错误，原订阅仍然有效',
    unauthorized: '登录凭证无效或缺少实时数据页面权限，请重新登录或联系管理员',
    redis_unavailable: 'Redis 暂时不可用，订阅已保留，连接恢复后将继续接收数据',
    internal_error: '实时服务内部错误，请稍后重试',
  }
  errorMessage.value = message.message || labels[message.code] || '实时服务发生错误'
  if (message.code === 'unauthorized') { snapshots.clear(); missingIds.value = []; rejectedIds.value = []; socket.disableForUnauthorized(); redirectToLogin() }
}

async function loadTree() {
  treeLoading.value = true
  try { tree.value = sortAssetTreeForDisplay(await fetchAssetTree()) }
  catch (error: any) { errorMessage.value = error?.message || '资产树加载失败' }
  finally { treeLoading.value = false }
}

function toggleBuilding(id: string) { expandedBuildings.has(id) ? expandedBuildings.delete(id) : expandedBuildings.add(id) }
function toggleFloor(id: string) { expandedFloors.has(id) ? expandedFloors.delete(id) : expandedFloors.add(id) }

async function selectNode(type: 'floor' | 'room', node: AssetTreeNode, floor: AssetTreeNode, building: AssetTreeNode) {
  const version = ++selectionVersion
  selection.value = { type, node, floor, building }
  snapshots.clear(); missingIds.value = []; rejectedIds.value = []; errorMessage.value = ''; infoMessage.value = ''
  clearFloorPlan()
  const terminalIds = (type === 'room' ? (node.sub_assets || []) : (floor.sub_assets || []).flatMap(room => room.sub_assets || [])).map(item => item.asset_id)
  socket.subscribe(terminalIds)
  void loadMetadata(terminalIds)
  if (type === 'floor') await loadFloorPlan(floor.asset_id, version)
}

async function loadMetadata(ids: string[]) {
  await Promise.all(ids.map(async id => {
    if (metadata.has(id) || metadataLoading.has(id)) return
    metadataLoading.add(id)
    try { metadata.set(id, await fetchTerminalTree(id)) }
    catch { /* ID 回退保证实时值仍可展示 */ }
    finally { metadataLoading.delete(id) }
  }))
}

async function loadFloorPlan(floorId: string, version: number) {
  planLoading.value = true
  try {
    const [data, image] = await Promise.all([fetchFloorPlan(floorId), fetchFloorPlanImage(floorId)])
    if (version !== selectionVersion) return
    floorPlan.value = data
    floorImageUrl.value = URL.createObjectURL(image)
  } catch {
    if (version === selectionVersion) floorPlan.value = null
  } finally { if (version === selectionVersion) planLoading.value = false }
}

function clearFloorPlan() {
  if (floorImageUrl.value) URL.revokeObjectURL(floorImageUrl.value)
  floorImageUrl.value = ''; floorPlan.value = null; planLoading.value = false
}

function terminalsForRoom(roomId: string) { return selectedRooms.value.find(room => room.asset_id === roomId)?.sub_assets || [] }
function terminalName(node: AssetTreeNode) { return metadata.get(node.asset_id)?.terminal_name || node.name || node.asset_id }
function terminalState(id: string) { return snapshots.get(id)?.terminal_status }
function sensorName(terminalId: string, sensorId: string) { return metadata.get(terminalId)?.sensors.find(item => item.sensor_id === sensorId)?.sensor_name || sensorId }
function pointName(terminalId: string, sensorId: string, pointId: string) { return metadata.get(terminalId)?.sensors.find(item => item.sensor_id === sensorId)?.points.find(item => item.point_id === pointId)?.point_name || pointId }
function pointUnit(terminalId: string, sensorId: string, pointId: string, unit: string) { return unit || metadata.get(terminalId)?.sensors.find(item => item.sensor_id === sensorId)?.points.find(item => item.point_id === pointId)?.point_unit || '' }
function formatValue(value: unknown) { return value === null || value === undefined || value === '' ? '--' : String(value) }
function formatTime(value: string) { const date = new Date(value); return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false }) }
function openControl(type: ControlAssetType, id: string, name: string) { controlTarget.value = { type, id, name } }
function regionStyle(region: FloorRoomRegion) {
  if (!floorPlan.value) return {}
  return { left: `${region.x / floorPlan.value.image_width * 100}%`, top: `${region.y / floorPlan.value.image_height * 100}%`, width: `${region.width / floorPlan.value.image_width * 100}%`, height: `${region.height / floorPlan.value.image_height * 100}%` }
}

const TerminalDetail = defineComponent({
  name: 'TerminalDetail',
  props: { terminal: { type: Object as PropType<AssetTreeNode>, required: true } },
  setup(props) {
    return () => {
      const terminal = props.terminal
      const snap = snapshots.get(terminal.asset_id)
      const state = snap?.terminal_status
      const header = h('div', { class: 'terminal-detail-head' }, [
        h('strong', terminalName(terminal)),
        h('div', { class: 'terminal-head-actions' }, [
          h('span', { class: state === true ? 'online' : state === false ? 'offline' : 'waiting' }, state === true ? '在线' : state === false ? '离线' : rejectedIds.value.includes(terminal.asset_id) ? '不可用' : '等待数据'),
          h('button', { class: 'inline-control', type: 'button', onClick: (event: Event) => { event.stopPropagation(); openControl('terminal', terminal.asset_id, terminalName(terminal)) } }, '控制'),
        ]),
      ])
      if (!snap) return h('section', { class: 'terminal-detail' }, [header, h('p', { class: 'muted' }, rejectedIds.value.includes(terminal.asset_id) ? '无权访问或资产不可用' : '等待首次数据')])
      const sensors = snap.sensor_list.map(sensor => h('div', { class: 'sensor-block', key: sensor.sensor_id }, [
        h('div', { class: 'sensor-title' }, [h('span', { class: ['sensor-dot', sensor.sensor_status ? 'online' : 'offline'] }), h('span', { class: 'sensor-name' }, sensorName(terminal.asset_id, sensor.sensor_id)), h('button', { class: 'inline-control sensor-control', type: 'button', onClick: (event: Event) => { event.stopPropagation(); openControl('sensor', sensor.sensor_id, sensorName(terminal.asset_id, sensor.sensor_id)) } }, '控制')]),
        sensor.point_list.length ? h('div', { class: 'point-grid' }, sensor.point_list.map(point => h('div', { class: 'point-row', key: point.point_id }, [
          h('span', pointName(terminal.asset_id, sensor.sensor_id, point.point_id)),
          h('b', `${formatValue(point.value)} ${pointUnit(terminal.asset_id, sensor.sensor_id, point.point_id, point.unit)}`.trim()),
        ]))) : h('p', { class: 'muted' }, '暂无测点'),
      ]))
      return h('section', { class: 'terminal-detail' }, [header, ...sensors, h('time', `数据时间：${formatTime(snap.time)}`)])
    }
  },
})

const RoomCard = defineComponent({
  name: 'RoomCard',
  props: { room: { type: Object as PropType<AssetTreeNode>, required: true } },
  setup(props) {
    return () => h('article', { class: 'room-card' }, [
      h('header', [h('h3', props.room.name), h('span', `${(props.room.sub_assets || []).length} 个终端`)]),
      (props.room.sub_assets || []).length
        ? h('div', { class: 'terminal-list' }, (props.room.sub_assets || []).map(terminal => h(TerminalDetail, { terminal, key: terminal.asset_id })))
        : h('p', { class: 'muted room-empty' }, '该房间暂无终端'),
    ])
  },
})

onMounted(loadTree)
onBeforeUnmount(() => { selectionVersion += 1; socket.stop(); clearFloorPlan() })
</script>

<template>
  <main class="page-content">
    <section class="workspace">
      <nav class="sibling-tabs">
        <button v-for="sib in siblings" :key="sib.route" class="sibling-tab" :class="{ active: route.path === sib.route }" @click="router.push(sib.route)">{{ sib.name }}</button>
      </nav>

      <header class="realtime-header">
        <div><h1>实时数据</h1><p>{{ selectedTitle }}</p></div>
        <div class="metrics">
          <span class="connection" :class="connectionState"><i></i>{{ connectionText }}</span>
          <span><b class="online-text">{{ onlineCount }}</b> 在线</span>
          <span><b class="offline-text">{{ offlineCount }}</b> 离线</span>
          <span class="last-time">更新：{{ latestTime ? formatTime(latestTime) : '--' }}</span>
        </div>
      </header>

      <div v-if="errorMessage || infoMessage" class="message" :class="errorMessage ? 'error' : 'info'">{{ errorMessage || infoMessage }}<button @click="errorMessage = ''; infoMessage = ''">×</button></div>

      <div class="content-layout">
        <section class="data-panel">
          <div v-if="!selection" class="empty-state"><div class="empty-icon">⌁</div><strong>请选择楼层或房间</strong><p>从右侧资产树选择需要监控的范围</p></div>
          <div v-else-if="!selectedTerminalIds.length" class="empty-state"><div class="empty-icon">○</div><strong>当前范围没有终端</strong><p>请先在资产管理中为房间添加终端</p></div>
          <div v-else-if="planLoading" class="empty-state"><span class="spinner"></span><strong>正在加载楼层平面图</strong></div>

          <template v-else-if="selection.type === 'floor' && floorPlan && floorPlan.regions.length">
            <div class="plan-scroll">
              <div class="plan-canvas">
                <img :src="floorImageUrl" alt="楼层平面图" draggable="false">
                <div v-for="region in floorPlan.regions" :key="region.room_id" class="plan-region" :style="regionStyle(region)">
                  <strong>{{ region.room_name }}</strong>
                  <div class="terminal-chips">
                    <span v-for="terminal in terminalsForRoom(region.room_id)" :key="terminal.asset_id" class="terminal-chip" :class="{ online: terminalState(terminal.asset_id) === true, offline: terminalState(terminal.asset_id) === false }">
                      <i></i>{{ terminalName(terminal) }}
                    </span>
                  </div>
                  <div class="region-popover">
                    <h3>{{ region.room_name }}</h3>
                    <TerminalDetail v-for="terminal in terminalsForRoom(region.room_id)" :key="terminal.asset_id" :terminal="terminal" />
                    <p v-if="!terminalsForRoom(region.room_id).length" class="muted">该房间暂无终端</p>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="unmarkedRooms.length" class="unmarked"><h2>未在平面图中标记的房间</h2><div class="room-grid"><RoomCard v-for="room in unmarkedRooms" :key="room.asset_id" :room="room" /></div></div>
          </template>

          <div v-else class="room-list-view">
            <div class="fallback-note" v-if="selection.type === 'floor'">该楼层未配置有效平面图，当前按房间展示实时数据</div>
            <div class="room-grid"><RoomCard v-for="room in selectedRooms" :key="room.asset_id" :room="room" /></div>
          </div>
        </section>

        <aside class="asset-tree-panel">
          <div class="tree-head"><div><h2>资产范围</h2><p>选择楼层或房间</p></div><span>{{ tree.length }} 个楼宇</span></div>
          <div v-if="treeLoading" class="tree-empty"><span class="spinner small"></span>加载中...</div>
          <div v-else-if="!tree.length" class="tree-empty">暂无可用资产</div>
          <div v-else class="tree-body">
            <div v-for="building in tree" :key="building.asset_id" class="tree-building">
              <button class="tree-row building" @click="toggleBuilding(building.asset_id)"><span class="arrow" :class="{ open: expandedBuildings.has(building.asset_id) }">›</span><span class="node-icon">▦</span><span>{{ building.name }}</span></button>
              <div v-if="expandedBuildings.has(building.asset_id)" class="tree-children">
                <div v-for="floor in building.sub_assets || []" :key="floor.asset_id">
                  <div class="floor-line">
                    <button class="fold-button" @click="toggleFloor(floor.asset_id)"><span class="arrow" :class="{ open: expandedFloors.has(floor.asset_id) }">›</span></button>
                    <button class="tree-row selectable" :class="{ selected: selection?.type === 'floor' && selection.node.asset_id === floor.asset_id }" @click="selectNode('floor', floor, floor, building)"><span class="node-icon">▤</span><span>{{ floor.name }}</span><small>{{ (floor.sub_assets || []).length }}</small></button>
                  </div>
                  <div v-if="expandedFloors.has(floor.asset_id)" class="room-children">
                    <button v-for="room in floor.sub_assets || []" :key="room.asset_id" class="tree-row selectable room" :class="{ selected: selection?.type === 'room' && selection.node.asset_id === room.asset_id }" @click="selectNode('room', room, floor, building)"><span class="node-icon">□</span><span>{{ room.name }}</span><small>{{ (room.sub_assets || []).length }}</small></button>
                    <p v-if="!(floor.sub_assets || []).length" class="no-child">暂无房间</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </section>
    <ControlExecutionModal
      :visible="!!controlTarget"
      :asset-id="controlTarget?.id ?? ''"
      :asset-type="controlTarget?.type ?? 'terminal'"
      :asset-name="controlTarget?.name ?? ''"
      @close="controlTarget = null"
    />
  </main>

</template>

<style scoped>
* { box-sizing: border-box; }.page-content { flex: 1; min-width: 0; padding: 28px 32px; overflow: hidden; color: #172033; }.workspace { height: calc(100vh - 56px); display: flex; flex-direction: column; min-height: 0; }
.sibling-tabs { display: flex; gap: 4px; padding: 4px; margin-bottom: 18px; border-radius: 14px; background: #fff; box-shadow: 0 4px 16px rgba(15,23,42,.05); flex-shrink: 0; overflow-x: auto; }.sibling-tab { padding: 10px 20px; border: 0; border-radius: 10px; background: transparent; color: #64748b; font-size: 14px; cursor: pointer; white-space: nowrap; }.sibling-tab:hover { background: #f1f5f9; }.sibling-tab.active { color: #fff; background: #3b82f6; }
.realtime-header { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-bottom: 16px; flex-shrink: 0; }.realtime-header h1 { margin: 0 0 5px; font-size: 24px; }.realtime-header p { margin: 0; color: #8492a6; font-size: 13px; }.metrics { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }.metrics > span { padding: 7px 11px; border: 1px solid #e2e8f0; border-radius: 8px; background: #fff; color: #64748b; font-size: 12px; }.metrics b { margin-right: 3px; }.online-text { color: #059669; }.offline-text { color: #dc2626; }.connection i,.terminal-chip i { display: inline-block; width: 7px; height: 7px; margin-right: 6px; border-radius: 50%; background: #94a3b8; }.connection.connected i { background: #10b981; box-shadow: 0 0 0 3px #d1fae5; }.connection.connecting i,.connection.reconnecting i { background: #f59e0b; animation: pulse 1s infinite; }.connection.unauthorized i { background: #ef4444; }.last-time { min-width: 170px; }
.message { display: flex; justify-content: space-between; padding: 10px 14px; margin-bottom: 12px; border-radius: 9px; font-size: 13px; flex-shrink: 0; }.message.error { color: #b91c1c; background: #fef2f2; }.message.info { color: #1d4ed8; background: #eff6ff; }.message button { border: 0; background: transparent; color: inherit; cursor: pointer; font-size: 17px; }
.content-layout { flex: 1; min-height: 0; display: grid; grid-template-columns: minmax(0,1fr) 290px; gap: 18px; }.data-panel,.asset-tree-panel { min-height: 0; overflow: hidden; border: 1px solid #e6ebf2; border-radius: 14px; background: #fff; box-shadow: 0 5px 18px rgba(15,23,42,.045); }.data-panel { display: flex; flex-direction: column; overflow-y: auto; }.empty-state { flex: 1; min-height: 360px; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #94a3b8; }.empty-state strong { margin: 10px 0 5px; color: #475569; }.empty-state p { margin: 0; font-size: 13px; }.empty-icon { width: 54px; height: 54px; display: grid; place-items: center; border-radius: 14px; background: #edf2f7; font-size: 28px; }.spinner { width: 25px; height: 25px; margin-bottom: 8px; border: 3px solid #dbeafe; border-top-color: #2563eb; border-radius: 50%; animation: spin .8s linear infinite; }.spinner.small { width: 16px; height: 16px; margin: 0 7px 0 0; border-width: 2px; }
.plan-scroll { flex-shrink: 0; min-height: 400px; padding: 22px; overflow: auto; display: flex; align-items: center; justify-content: center; background: #f8fafc; }.plan-canvas { position: relative; max-width: 100%; line-height: 0; box-shadow: 0 5px 20px rgba(15,23,42,.16); }.plan-canvas > img { display: block; max-width: 100%; max-height: calc(100vh - 285px); user-select: none; }.plan-region { position: absolute; z-index: 1; min-width: 45px; min-height: 38px; padding: 6px; border: 2px solid #64748b; background: rgba(255,255,255,.78); line-height: 1.25; cursor: default; }.plan-region > strong { display: block; overflow: hidden; color: #172033; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }.terminal-chips { display: flex; flex-wrap: wrap; gap: 3px; margin-top: 4px; }.terminal-chip { max-width: 100%; padding: 2px 4px; border-radius: 4px; color: #64748b; background: #e2e8f0; font-size: 9px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.terminal-chip i { width: 5px; height: 5px; margin-right: 3px; }.terminal-chip.online { color: #047857; background: #d1fae5; }.terminal-chip.online i { background: #10b981; }.terminal-chip.offline { color: #b91c1c; background: #fee2e2; }.terminal-chip.offline i { background: #ef4444; }.region-popover { display: none; position: absolute; z-index: 20; left: calc(100% + 8px); top: 0; width: 310px; max-height: 360px; padding: 14px; overflow: auto; border: 1px solid #dbe3ee; border-radius: 10px; background: #fff; box-shadow: 0 15px 40px rgba(15,23,42,.22); line-height: 1.4; }.plan-region:hover { z-index: 10; border-color: #2563eb; }.plan-region:hover .region-popover { display: block; }.region-popover h3 { margin: 0 0 10px; font-size: 14px; }
.unmarked { padding: 18px; border-top: 1px solid #e2e8f0; }.unmarked h2 { margin: 0 0 12px; font-size: 15px; }.room-list-view { padding: 18px; }.fallback-note { margin-bottom: 14px; padding: 10px 13px; border-radius: 8px; color: #92400e; background: #fffbeb; font-size: 12px; }.room-grid { display: grid; grid-template-columns: repeat(auto-fit,minmax(360px,1fr)); align-items: start; gap: 14px; }
.room-card { min-width: 0; overflow: hidden; border: 1px solid #e2e8f0; border-radius: 11px; background: #fff; }.room-card > header { display: flex; align-items: center; justify-content: space-between; padding: 12px 14px; background: #f8fafc; border-bottom: 1px solid #e2e8f0; }.room-card > header h3 { margin: 0; font-size: 14px; }.room-card > header span { color: #94a3b8; font-size: 11px; }.room-empty { padding: 14px; }
.terminal-detail { padding: 11px 14px; border-bottom: 1px solid #f1f5f9; }.terminal-detail:last-child { border-bottom: 0; }.terminal-detail-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }.terminal-detail-head strong { font-size: 13px; }.terminal-detail-head span { padding: 2px 7px; border-radius: 10px; font-size: 10px; }.terminal-detail-head .online { color: #047857; background: #d1fae5; }.terminal-detail-head .offline { color: #b91c1c; background: #fee2e2; }.terminal-detail-head .waiting { color: #64748b; background: #e2e8f0; }.sensor-block { margin-top: 7px; padding: 8px; border-radius: 7px; background: #f8fafc; }.sensor-title { display: flex; align-items: center; color: #475569; font-size: 11px; font-weight: 600; }.sensor-dot { width: 6px; height: 6px; margin-right: 5px; border-radius: 50%; }.sensor-dot.online { background: #10b981; }.sensor-dot.offline { background: #ef4444; }.point-grid { margin-top: 5px; }.point-row { display: flex; justify-content: space-between; gap: 8px; padding: 3px 0; color: #64748b; font-size: 11px; }.point-row b { color: #172033; font-weight: 600; text-align: right; }.terminal-detail time { display: block; margin-top: 7px; color: #94a3b8; font-size: 9px; }.muted { margin: 6px 0 0; color: #94a3b8; font-size: 11px; }
/* h() 创建的局部组件需要 deep 选择器才能命中其内部节点。 */
:deep(.room-card > header) { display: flex; align-items: center; justify-content: space-between; padding: 12px 14px; background: #f8fafc; border-bottom: 1px solid #e2e8f0; }
:deep(.room-card > header h3) { margin: 0; font-size: 14px; }
:deep(.room-card > header span) { color: #94a3b8; font-size: 11px; }
:deep(.terminal-list) { display: flex; flex-direction: column; gap: 10px; padding: 12px; background: #f8fafc; }
:deep(.terminal-list > .terminal-detail) { padding: 12px; border: 1px solid #e2e8f0; border-left: 3px solid #94a3b8; border-radius: 9px; background: #fff; box-shadow: 0 2px 6px rgba(15,23,42,.035); }
:deep(.terminal-list > .terminal-detail:has(.terminal-detail-head .online)) { border-left-color: #10b981; }
:deep(.terminal-list > .terminal-detail:has(.terminal-detail-head .offline)) { border-left-color: #ef4444; }
:deep(.terminal-detail-head) { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
:deep(.terminal-detail-head strong) { font-size: 13px; }
:deep(.terminal-detail-head span) { padding: 2px 7px; border-radius: 10px; font-size: 10px; }
:deep(.terminal-detail-head .online) { color: #047857; background: #d1fae5; }
:deep(.terminal-detail-head .offline) { color: #b91c1c; background: #fee2e2; }
:deep(.terminal-detail-head .waiting) { color: #64748b; background: #e2e8f0; }
:deep(.terminal-head-actions) { display: flex; align-items: center; gap: 6px; }
:deep(.inline-control) { height: 25px; padding: 0 9px; border: 1px solid #bfdbfe; border-radius: 6px; color: #2563eb; background: #eff6ff; font-size: 10px; cursor: pointer; }
:deep(.inline-control:hover) { border-color: #93c5fd; background: #dbeafe; }
:deep(.sensor-name) { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
:deep(.sensor-control) { flex: none; margin-left: auto; }
:deep(.sensor-block) { margin-top: 8px; padding: 10px; border: 1px solid #edf1f6; border-radius: 7px; background: #f8fafc; }
:deep(.sensor-title) { display: flex; align-items: center; color: #475569; font-size: 11px; font-weight: 600; }
:deep(.sensor-dot) { width: 6px; height: 6px; margin-right: 5px; border-radius: 50%; }
:deep(.sensor-dot.online) { background: #10b981; }:deep(.sensor-dot.offline) { background: #ef4444; }
:deep(.point-grid) { display: grid; grid-template-columns: repeat(auto-fit,minmax(125px,1fr)); gap: 6px; margin-top: 8px; }
:deep(.point-row) { min-width: 0; display: flex; flex-direction: column; gap: 3px; padding: 7px 8px; border-radius: 6px; color: #64748b; background: #fff; font-size: 10px; }
:deep(.point-row span) { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
:deep(.point-row b) { overflow-wrap: anywhere; color: #172033; font-size: 12px; font-weight: 650; text-align: left; }
:deep(.terminal-detail time) { display: block; margin-top: 7px; color: #94a3b8; font-size: 9px; }:deep(.muted) { margin: 6px 0 0; color: #94a3b8; font-size: 11px; }
.asset-tree-panel { display: flex; flex-direction: column; }.tree-head { display: flex; justify-content: space-between; align-items: center; padding: 16px; border-bottom: 1px solid #e2e8f0; }.tree-head h2 { margin: 0 0 3px; font-size: 16px; }.tree-head p,.tree-head > span { margin: 0; color: #94a3b8; font-size: 11px; }.tree-body { flex: 1; padding: 8px; overflow-y: auto; }.tree-empty { flex: 1; display: flex; align-items: center; justify-content: center; color: #94a3b8; font-size: 12px; }.tree-row { min-width: 0; height: 36px; display: flex; align-items: center; gap: 7px; border: 0; border-radius: 7px; background: transparent; color: #475569; text-align: left; cursor: pointer; }.tree-row span:last-of-type { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.tree-row:hover { background: #f1f5f9; }.tree-row.building { width: 100%; padding: 0 8px; font-weight: 600; }.tree-children { padding-left: 15px; }.floor-line { display: flex; align-items: center; }.fold-button { width: 24px; height: 34px; border: 0; background: none; cursor: pointer; }.floor-line .tree-row { flex: 1; }.room-children { padding-left: 28px; }.tree-row.room { width: 100%; padding: 0 8px; }.tree-row.selectable.selected { color: #1d4ed8; background: #dbeafe; font-weight: 600; }.tree-row small { padding-right: 7px; color: #94a3b8; font-size: 10px; }.arrow { display: inline-block; color: #94a3b8; transition: transform .15s; }.arrow.open { transform: rotate(90deg); }.node-icon { flex: none !important; color: #64748b; }.no-child { margin: 5px 8px; color: #94a3b8; font-size: 11px; }
@keyframes spin { to { transform: rotate(360deg); } }@keyframes pulse { 50% { opacity: .35; } }
@media (max-width: 1050px) { .content-layout { grid-template-columns: minmax(0,1fr) 245px; }.metrics .last-time { display: none; } }
@media (max-width: 800px) { .page-content { overflow: auto; }.workspace { height: auto; min-height: calc(100vh - 56px); }.realtime-header { align-items: flex-start; flex-direction: column; }.content-layout { grid-template-columns: 1fr; }.data-panel { min-height: 520px; }.asset-tree-panel { min-height: 400px; } }
</style>
