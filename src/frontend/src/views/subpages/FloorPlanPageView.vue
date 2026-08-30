<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchAssetTree, type AssetTreeNode } from '../../api/asset'
import {
  deleteFloorPlan, fetchFloorPlan, fetchFloorPlanImage, saveFloorPlanRegions, uploadFloorPlan,
  type FloorPlan, type FloorRoomRegion,
} from '../../api/floorPlan'
import { isMenuGroup, menuConfig } from '../../config/menu'
import ConfirmModal from '../modals/ConfirmModal.vue'

const route = useRoute()
const router = useRouter()
const siblings = computed(() => {
  for (const entry of menuConfig) if (isMenuGroup(entry) && entry.children.some(item => item.route === route.path)) return entry.children
  return []
})

const buildings = ref<AssetTreeNode[]>([])
const buildingId = ref('')
const floorId = ref('')
const loadingTree = ref(false)
const loadingPlan = ref(false)
const actionLoading = ref(false)
const error = ref('')
const notice = ref('')
const plan = ref<FloorPlan | null>(null)
const imageObjectUrl = ref('')
const draftRegions = ref<FloorRoomRegion[]>([])
const selectedRoomId = ref('')
const canvas = ref<HTMLElement | null>(null)
const drawing = ref<{ roomId: string; startX: number; startY: number; x: number; y: number; width: number; height: number } | null>(null)
const dirty = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const confirmMode = ref<'replace' | 'delete' | 'clear' | null>(null)
const pendingFile = ref<File | null>(null)

const floors = computed(() => buildings.value.find(item => item.asset_id === buildingId.value)?.sub_assets || [])
const rooms = computed(() => floors.value.find(item => item.asset_id === floorId.value)?.sub_assets || [])
const currentFloor = computed(() => floors.value.find(item => item.asset_id === floorId.value))
const markedIds = computed(() => new Set(draftRegions.value.map(item => item.room_id)))
const availableRooms = computed(() => rooms.value.filter(item => !markedIds.value.has(item.asset_id)))
const hasPlan = computed(() => !!plan.value)

function clearMessages() { error.value = ''; notice.value = '' }
function revokeImage() { if (imageObjectUrl.value) URL.revokeObjectURL(imageObjectUrl.value); imageObjectUrl.value = '' }

async function loadTree() {
  loadingTree.value = true
  try {
    buildings.value = await fetchAssetTree()
    buildingId.value = buildings.value[0]?.asset_id || ''
    floorId.value = ''
  } catch (e: any) { error.value = e?.message || '加载资产树失败' }
  finally { loadingTree.value = false }
}

async function loadPlan() {
  revokeImage(); plan.value = null; draftRegions.value = []; selectedRoomId.value = ''; dirty.value = false
  if (!floorId.value) return
  loadingPlan.value = true; clearMessages()
  try {
    const data = await fetchFloorPlan(floorId.value)
    const blob = await fetchFloorPlanImage(floorId.value)
    plan.value = data
    draftRegions.value = data.regions.map(item => ({ ...item }))
    imageObjectUrl.value = URL.createObjectURL(blob)
  } catch (e: any) {
    // 未上传平面图是正常空状态；保留其他错误供用户排查。
    if (!String(e?.message || '').includes('404') && !String(e?.message || '').includes('不存在')) error.value = e?.message || '加载平面图失败'
  } finally { loadingPlan.value = false }
}

// 切换楼宇后由用户明确选择楼层，避免自动请求任意楼层的平面图。
watch(buildingId, () => { floorId.value = '' })
watch(floorId, loadPlan)

function chooseFile() { fileInput.value?.click() }
function onFileSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  clearMessages()
  if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) { error.value = '仅支持 PNG、JPEG 或 WebP 图片'; return }
  if (file.size > 10 * 1024 * 1024) { error.value = '图片不能超过 10MB'; return }
  pendingFile.value = file
  if (hasPlan.value) confirmMode.value = 'replace'
  else performUpload()
}

async function performUpload() {
  if (!pendingFile.value || !floorId.value) return
  const replacing = hasPlan.value
  actionLoading.value = true; clearMessages()
  try {
    await uploadFloorPlan(floorId.value, pendingFile.value)
    confirmMode.value = null; pendingFile.value = null
    await loadPlan()
    notice.value = replacing ? '平面图已替换，原有房间标记已清空' : '平面图上传成功'
  } catch (e: any) { error.value = e?.message || '上传失败' }
  finally { actionLoading.value = false }
}

function originalPoint(event: PointerEvent) {
  const rect = canvas.value!.getBoundingClientRect()
  return {
    x: Math.max(0, Math.min(plan.value!.image_width, (event.clientX - rect.left) / rect.width * plan.value!.image_width)),
    y: Math.max(0, Math.min(plan.value!.image_height, (event.clientY - rect.top) / rect.height * plan.value!.image_height)),
  }
}

function startDraw(event: PointerEvent) {
  if (!selectedRoomId.value || !plan.value || !canvas.value) return
  const point = originalPoint(event)
  drawing.value = { roomId: selectedRoomId.value, startX: point.x, startY: point.y, x: point.x, y: point.y, width: 0, height: 0 }
  canvas.value.setPointerCapture(event.pointerId)
}
function moveDraw(event: PointerEvent) {
  if (!drawing.value) return
  const p = originalPoint(event); const d = drawing.value
  d.x = Math.min(d.startX, p.x); d.y = Math.min(d.startY, p.y)
  d.width = Math.abs(p.x - d.startX); d.height = Math.abs(p.y - d.startY)
}
function endDraw(event: PointerEvent) {
  if (!drawing.value || !plan.value) return
  canvas.value?.releasePointerCapture(event.pointerId)
  const d = drawing.value; drawing.value = null
  const width = Math.round(d.width); const height = Math.round(d.height)
  if (width < 4 || height < 4) return
  const room = rooms.value.find(item => item.asset_id === d.roomId)
  draftRegions.value.push({ room_id: d.roomId, room_name: room?.name || d.roomId, x: Math.round(d.x), y: Math.round(d.y), width, height })
  selectedRoomId.value = ''; dirty.value = true
}

function regionStyle(region: Pick<FloorRoomRegion, 'x' | 'y' | 'width' | 'height'>) {
  if (!plan.value) return {}
  return { left: `${region.x / plan.value.image_width * 100}%`, top: `${region.y / plan.value.image_height * 100}%`, width: `${region.width / plan.value.image_width * 100}%`, height: `${region.height / plan.value.image_height * 100}%` }
}
function removeRegion(roomId: string) { draftRegions.value = draftRegions.value.filter(item => item.room_id !== roomId); dirty.value = true }

async function saveRegions() {
  if (!plan.value) return
  actionLoading.value = true; clearMessages()
  try {
    const saved = await saveFloorPlanRegions(floorId.value, draftRegions.value.map(({ room_id, x, y, width, height }) => ({ room_id, x, y, width, height })))
    plan.value = saved; draftRegions.value = saved.regions.map(item => ({ ...item })); dirty.value = false; notice.value = '房间标记已保存'
  } catch (e: any) { error.value = e?.message || '保存失败' }
  finally { actionLoading.value = false }
}
async function clearRegions() {
  actionLoading.value = true; clearMessages()
  try { const saved = await saveFloorPlanRegions(floorId.value, []); plan.value = saved; draftRegions.value = []; dirty.value = false; notice.value = '房间标记已清空'; confirmMode.value = null }
  catch (e: any) { error.value = e?.message || '清空失败' }
  finally { actionLoading.value = false }
}
async function removePlan() {
  actionLoading.value = true; clearMessages()
  try { await deleteFloorPlan(floorId.value); revokeImage(); plan.value = null; draftRegions.value = []; dirty.value = false; notice.value = '平面图已删除'; confirmMode.value = null }
  catch (e: any) { error.value = e?.message || '删除失败' }
  finally { actionLoading.value = false }
}
function confirmAction() { if (confirmMode.value === 'replace') performUpload(); else if (confirmMode.value === 'delete') removePlan(); else if (confirmMode.value === 'clear') clearRegions() }
const confirmCopy = computed(() => ({
  replace: ['替换平面图', '替换后旧图片会被删除，该楼层的全部房间标记也会清空。确定继续吗？', '确认替换'],
  delete: ['删除平面图', '将删除平面图图片及该楼层的全部房间标记，此操作不可恢复。', '确认删除'],
  clear: ['清空房间标记', '确定清空该楼层的全部房间标记吗？', '确认清空'],
}[confirmMode.value || 'delete']))

onMounted(loadTree)
onBeforeUnmount(revokeImage)
</script>

<template>
  <main class="page-content">
    <section class="workspace">

      <div class="page-head">
        <div><h1>楼层平面图</h1><p>上传楼层图纸，并在原图坐标上标记房间区域</p></div>
        <div class="selectors">
          <label>楼宇<select v-model="buildingId" :disabled="loadingTree"><option v-for="item in buildings" :key="item.asset_id" :value="item.asset_id">{{ item.name }}</option></select></label>
          <label>楼层<select v-model="floorId" :disabled="!floors.length"><option value="" disabled>{{ floors.length ? '请选择楼层' : '该楼宇暂无楼层' }}</option><option v-for="item in floors" :key="item.asset_id" :value="item.asset_id">{{ item.name }}</option></select></label>
        </div>
      </div>

      <div v-if="error || notice" class="message" :class="error ? 'error' : 'success'">{{ error || notice }}<button @click="clearMessages">×</button></div>

      <div class="main-grid">
        <section class="plan-card">
          <div class="card-toolbar">
            <div><strong>{{ currentFloor?.name || '请选择楼层' }}</strong><span v-if="plan">{{ plan.image_width }} × {{ plan.image_height }} · {{ plan.image_type }}</span></div>
            <div class="actions">
              <input ref="fileInput" type="file" accept="image/png,image/jpeg,image/webp" hidden @change="onFileSelected">
              <button class="btn secondary" :disabled="!floorId || actionLoading" @click="chooseFile">{{ plan ? '替换图片' : '上传图片' }}</button>
              <button v-if="plan" class="btn danger-ghost" :disabled="actionLoading" @click="confirmMode = 'delete'">删除</button>
            </div>
          </div>

          <div class="stage-wrap">
            <div v-if="loadingPlan" class="empty"><span class="spinner"></span>正在加载平面图...</div>
            <div v-else-if="!floorId" class="empty"><div class="empty-icon">⌁</div><strong>请先选择要添加平面图的楼层</strong><p>{{ floors.length ? '从右上角的楼层下拉框中选择楼层' : '当前楼宇暂无楼层，请先在资产树中创建' }}</p></div>
            <div v-else-if="!plan" class="empty"><div class="empty-icon">▧</div><strong>该楼层还没有平面图</strong><p>支持 PNG、JPEG、WebP，文件最大 10MB</p><button class="btn primary" @click="chooseFile">选择图片上传</button></div>
            <div v-else class="image-stage">
              <div ref="canvas" class="canvas" :class="{ drawing: selectedRoomId }" @pointerdown="startDraw" @pointermove="moveDraw" @pointerup="endDraw" @pointercancel="drawing = null">
                <img :src="imageObjectUrl" alt="楼层平面图" draggable="false">
                <div v-for="(region, index) in draftRegions" :key="region.room_id" class="region" :style="regionStyle(region)">
                  <span class="region-index">{{ index + 1 }}</span><span class="region-name">{{ region.room_name }}</span>
                </div>
                <div v-if="drawing" class="region draft" :style="regionStyle(drawing)"></div>
              </div>
            </div>
          </div>
          <div v-if="plan" class="status-bar"><span>共 {{ draftRegions.length }} 个房间标记</span><span v-if="selectedRoomId" class="draw-tip">在图上按住并拖动，绘制房间区域</span><span v-else>请选择右侧未标记房间开始绘制</span></div>
        </section>

        <aside class="room-card">
          <div class="room-head"><div><h2>房间标记</h2><span>{{ draftRegions.length }} / {{ rooms.length }}</span></div><button v-if="draftRegions.length" class="link-danger" @click="confirmMode = 'clear'">全部清空</button></div>
          <div v-if="!plan" class="side-empty">上传平面图后可添加房间标记</div>
          <template v-else>
            <div class="picker"><label>选择未标记房间</label><select v-model="selectedRoomId" :disabled="!availableRooms.length"><option value="">{{ availableRooms.length ? '请选择房间' : '所有房间均已标记' }}</option><option v-for="room in availableRooms" :key="room.asset_id" :value="room.asset_id">{{ room.name }}</option></select><p>选择后在平面图上拖动鼠标绘制矩形</p></div>
            <div class="region-list">
              <div v-for="(region, index) in draftRegions" :key="region.room_id" class="region-item"><span class="number">{{ index + 1 }}</span><div><strong>{{ region.room_name }}</strong><small>X {{ region.x }} · Y {{ region.y }} · {{ region.width }} × {{ region.height }}</small></div><button title="删除标记" @click="removeRegion(region.room_id)">×</button></div>
              <div v-if="!draftRegions.length" class="side-empty compact">暂无标记</div>
            </div>
            <div class="save-area"><span v-if="dirty">有未保存的更改</span><button class="btn primary" :disabled="!dirty || actionLoading" @click="saveRegions">{{ actionLoading ? '处理中...' : '保存全部标记' }}</button></div>
          </template>
        </aside>
      </div>
    </section>
    <ConfirmModal :visible="!!confirmMode" :title="confirmCopy[0]!" :message="confirmCopy[1]!" :confirm-text="confirmCopy[2]!" :danger="true" :loading="actionLoading" :error="error" @confirm="confirmAction" @cancel="confirmMode = null; pendingFile = null" />
  </main>
</template>

<style scoped>
* { box-sizing: border-box; }
.page-content { flex: 1; min-width: 0; padding: 28px 32px; overflow: hidden; color: #172033; }
.workspace { height: calc(100vh - 56px); display: flex; flex-direction: column; min-height: 0; }
.sibling-tabs { display: flex; gap: 4px; padding: 4px; margin-bottom: 20px; border-radius: 14px; background: #fff; box-shadow: 0 4px 16px rgba(15,23,42,.05); flex-shrink: 0; overflow-x: auto; }
.sibling-tab { padding: 10px 20px; border: 0; border-radius: 10px; background: transparent; color: #64748b; font-size: 14px; cursor: pointer; white-space: nowrap; }
.sibling-tab:hover { background: #f1f5f9; }.sibling-tab.active { color: #fff; background: #3b82f6; }
.page-head { display: flex; justify-content: space-between; align-items: end; gap: 24px; margin-bottom: 18px; flex-shrink: 0; }
.page-head h1 { margin: 0 0 5px; font-size: 24px; }.page-head p { margin: 0; color: #8492a6; font-size: 13px; }
.selectors { display: flex; gap: 12px; }.selectors label,.picker label { color: #64748b; font-size: 12px; font-weight: 600; }
select { display: block; min-width: 180px; height: 38px; margin-top: 6px; padding: 0 34px 0 12px; border: 1px solid #dbe3ee; border-radius: 9px; background: #fff; color: #334155; outline: none; }
select:focus { border-color: #3b82f6; box-shadow: 0 0 0 3px #dbeafe; }
.message { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; margin-bottom: 12px; border-radius: 9px; font-size: 13px; flex-shrink: 0; }.message.error { background: #fef2f2; color: #b91c1c; }.message.success { background: #ecfdf5; color: #047857; }.message button { border: 0; background: none; color: inherit; cursor: pointer; font-size: 18px; }
.main-grid { display: grid; grid-template-columns: minmax(0,1fr) 320px; gap: 18px; flex: 1; min-height: 0; }
.plan-card,.room-card { background: #fff; border: 1px solid #e6ebf2; border-radius: 14px; box-shadow: 0 5px 18px rgba(15,23,42,.045); min-height: 0; overflow: hidden; }
.plan-card { display: flex; flex-direction: column; }.card-toolbar { height: 62px; padding: 0 18px; border-bottom: 1px solid #edf1f6; display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; }.card-toolbar strong { font-size: 15px; }.card-toolbar span { margin-left: 12px; color: #94a3b8; font-size: 12px; }.actions { display: flex; gap: 8px; }
.btn { height: 36px; padding: 0 15px; border: 0; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; }.btn:disabled { opacity: .45; cursor: not-allowed; }.btn.primary { color: #fff; background: #2563eb; }.btn.primary:hover:not(:disabled) { background: #1d4ed8; }.btn.secondary { color: #334155; background: #eef2f7; }.btn.danger-ghost { color: #dc2626; background: #fff1f2; }
.stage-wrap { flex: 1; min-height: 0; display: flex; padding: 18px; background-color: #f8fafc; background-image: linear-gradient(45deg,#eef2f7 25%,transparent 25%),linear-gradient(-45deg,#eef2f7 25%,transparent 25%),linear-gradient(45deg,transparent 75%,#eef2f7 75%),linear-gradient(-45deg,transparent 75%,#eef2f7 75%); background-size: 18px 18px; background-position: 0 0,0 9px,9px -9px,-9px 0; }
.image-stage { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; overflow: hidden; }.canvas { position: relative; max-width: 100%; max-height: 100%; line-height: 0; user-select: none; box-shadow: 0 4px 18px rgba(15,23,42,.16); touch-action: none; }.canvas.drawing { cursor: crosshair; }.canvas img { display: block; max-width: 100%; max-height: calc(100vh - 310px); width: auto; height: auto; pointer-events: none; }
.region { position: absolute; border: 2px solid #2563eb; background: rgba(37,99,235,.16); line-height: normal; pointer-events: none; min-width: 2px; min-height: 2px; }.region.draft { border-style: dashed; background: rgba(16,185,129,.18); }.region-index { position: absolute; left: -9px; top: -9px; width: 19px; height: 19px; border-radius: 50%; display: grid; place-items: center; background: #2563eb; color: white; font-size: 10px; font-weight: 700; }.region-name { position: absolute; left: 6px; top: 6px; padding: 3px 6px; border-radius: 4px; color: white; background: rgba(30,64,175,.86); font-size: 11px; white-space: nowrap; }
.empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #94a3b8; font-size: 13px; }.empty strong { color: #475569; font-size: 15px; margin: 6px 0; }.empty p { margin: 0 0 18px; }.empty-icon { width: 54px; height: 54px; display: grid; place-items: center; border-radius: 14px; background: #e8eef7; color: #64748b; font-size: 28px; }.spinner { width: 24px; height: 24px; margin-bottom: 10px; border: 3px solid #dbeafe; border-top-color: #2563eb; border-radius: 50%; animation: spin .8s linear infinite; }@keyframes spin { to { transform: rotate(360deg); } }
.status-bar { height: 42px; padding: 0 18px; border-top: 1px solid #edf1f6; display: flex; align-items: center; justify-content: space-between; color: #94a3b8; font-size: 12px; flex-shrink: 0; }.draw-tip { color: #2563eb; font-weight: 600; }
.room-card { display: flex; flex-direction: column; }.room-head { height: 62px; padding: 0 18px; border-bottom: 1px solid #edf1f6; display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; }.room-head h2 { display: inline; margin: 0; font-size: 16px; }.room-head span { margin-left: 8px; color: #94a3b8; font-size: 12px; }.link-danger { border: 0; background: none; color: #dc2626; font-size: 12px; cursor: pointer; }
.picker { padding: 16px 18px; border-bottom: 1px solid #edf1f6; }.picker select { width: 100%; min-width: 0; }.picker p { margin: 8px 0 0; color: #94a3b8; font-size: 11px; }.region-list { flex: 1; padding: 8px 10px; overflow-y: auto; }.region-item { display: flex; align-items: center; gap: 10px; padding: 10px 8px; border-bottom: 1px solid #f1f5f9; }.region-item .number { width: 22px; height: 22px; display: grid; place-items: center; border-radius: 6px; color: #2563eb; background: #eff6ff; font-size: 11px; font-weight: 700; }.region-item div { flex: 1; min-width: 0; }.region-item strong,.region-item small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.region-item strong { color: #334155; font-size: 13px; }.region-item small { margin-top: 3px; color: #94a3b8; font-size: 10px; }.region-item button { border: 0; background: none; color: #94a3b8; font-size: 19px; cursor: pointer; }.region-item button:hover { color: #dc2626; }
.side-empty { flex: 1; display: grid; place-items: center; padding: 25px; color: #94a3b8; text-align: center; font-size: 13px; }.side-empty.compact { display: block; }.save-area { padding: 14px 16px; border-top: 1px solid #edf1f6; flex-shrink: 0; }.save-area span { display: block; margin-bottom: 8px; color: #d97706; font-size: 11px; }.save-area .btn { width: 100%; }
@media (max-width: 1000px) { .main-grid { grid-template-columns: 1fr; overflow-y: auto; }.plan-card { min-height: 560px; }.room-card { min-height: 400px; }.page-head { align-items: flex-start; flex-direction: column; }.workspace { overflow-y: auto; }.main-grid { flex: none; }.selectors { width: 100%; }.selectors label,.selectors select { flex: 1; width: 100%; min-width: 0; } }
</style>
