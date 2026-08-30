<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getCurrentUser } from '../../api/auth'
import { fetchDashboardOverview, type DashboardAssetStatistic, type DashboardOverview, type DashboardPageItem } from '../../api/dashboard'
import { isMenuGroup, menuConfig } from '../../config/menu'

const router = useRouter()
const user = getCurrentUser() || { nickname: '游客' }
const nickname = computed(() => user.nickname || '游客')
const overview = ref<DashboardOverview | null>(null)
const loading = ref(false)
const error = ref('')
const updatedAt = ref<Date | null>(null)

const routeMap = new Map<string, string>()
for (const entry of menuConfig) {
  if (isMenuGroup(entry)) entry.children.forEach(child => routeMap.set(child.path_code, child.route))
  else routeMap.set(entry.path_code, entry.route)
}

const assetCards = computed(() => {
  const statistics = overview.value?.statistics
  return [
    { key: 'building', name: '楼宇', icon: '/icon/asset_building_black.png', tone: 'blue', value: statistics?.building },
    { key: 'floor', name: '楼层', icon: '/icon/asset_floor_black.png', tone: 'cyan', value: statistics?.floor },
    { key: 'room', name: '房间', icon: '/icon/asset_room_black.png', tone: 'violet', value: statistics?.room },
    { key: 'terminal', name: '终端', icon: '/icon/asset_terminal_black.png', tone: 'orange', value: statistics?.terminal },
    { key: 'sensor', name: '传感器', icon: '/icon/asset_sensor_black.png', tone: 'green', value: statistics?.sensor },
  ] as { key: string; name: string; icon: string; tone: string; value?: DashboardAssetStatistic }[]
})

const businessCards = computed(() => {
  const statistics = overview.value?.statistics
  return [
    { name: '系统用户', value: statistics?.user_count ?? 0, symbol: '人', tone: 'blue' },
    { name: '采集请求', value: statistics?.request_count ?? 0, symbol: '采', tone: 'violet' },
    { name: '控制项目', value: statistics?.control_count ?? 0, symbol: '控', tone: 'orange' },
    { name: '自动规则', value: statistics?.rule_count ?? 0, symbol: '规', tone: 'green' },
  ]
})

const enabledAssetTotal = computed(() => assetCards.value.reduce((sum, item) => sum + (item.value?.enabled_total ?? 0), 0))
const onlineDeviceTotal = computed(() => (overview.value?.statistics.terminal.online_count ?? 0) + (overview.value?.statistics.sensor.online_count ?? 0))
const enabledDeviceTotal = computed(() => (overview.value?.statistics.terminal.enabled_total ?? 0) + (overview.value?.statistics.sensor.enabled_total ?? 0))
const onlineRate = computed(() => enabledDeviceTotal.value ? Math.round(onlineDeviceTotal.value / enabledDeviceTotal.value * 100) : 0)

function onlinePercent(statistic?: DashboardAssetStatistic) {
  if (!statistic?.enabled_total) return 0
  return Math.round((statistic.online_count ?? 0) / statistic.enabled_total * 100)
}

function pageRoute(item: DashboardPageItem) { return routeMap.get(item.key) || '' }

function pageIcon(key: string) {
  if (key.startsWith('asset')) return '/icon/page_asset_white.png'
  if (key.startsWith('data')) return '/icon/page_data_white.png'
  if (key.startsWith('channel')) return '/icon/page_channel_white.png'
  if (key.startsWith('user')) return '/icon/page_user_white.png'
  if (key.startsWith('rule')) return '/icon/page_rules_white.png'
  if (key.startsWith('log')) return '/icon/page_logs_white.png'
  if (key.toLowerCase().includes('floorplan')) return '/icon/page_floorplan_white.png'
  return '/icon/page_dashboard_white.png'
}

async function loadOverview() {
  loading.value = true
  error.value = ''
  try {
    overview.value = await fetchDashboardOverview()
    updatedAt.value = new Date()
  } catch (e: any) {
    error.value = e?.message || '看板数据加载失败'
  } finally { loading.value = false }
}

function openPage(item: DashboardPageItem) {
  const route = pageRoute(item)
  if (route) router.push(route)
}

onMounted(loadOverview)
</script>

<template>
  <main class="dashboard-page">
    <section class="hero-card">
      <div class="hero-copy">
        <span class="eyebrow">SMART BUILDING OVERVIEW</span>
        <h1>欢迎回来，{{ nickname }}</h1>
        <p>在一个看板中掌握授权资产的启用情况、设备在线状态与系统配置规模。</p>
        <div class="hero-meta">
          <span><i class="pulse-dot"></i>设备在线率 {{ onlineRate }}%</span>
          <span v-if="updatedAt">更新于 {{ updatedAt.toLocaleTimeString('zh-CN', { hour12: false }) }}</span>
        </div>
      </div>
      <div class="hero-summary">
        <div><strong>{{ enabledAssetTotal }}</strong><span>可见启用资产</span></div>
        <div><strong>{{ onlineDeviceTotal }}</strong><span>在线终端与传感器</span></div>
        <button :disabled="loading" @click="loadOverview"><span :class="{ rotating: loading }">↻</span>{{ loading ? '正在刷新' : '刷新概览' }}</button>
      </div>
    </section>

    <div v-if="error" class="error-banner">
      <span><b>!</b>{{ error }}</span><button @click="loadOverview">重新加载</button>
    </div>

    <div class="dashboard-layout">
      <div class="dashboard-left">
        <section class="dashboard-section asset-section">
          <header class="section-title">
            <div><h2>资产运行概览</h2><p>仅统计当前用户可见且已经启用的资产</p></div><span>共 {{ enabledAssetTotal }} 项</span>
          </header>
          <div class="asset-grid" :class="{ skeleton: loading && !overview }">
            <article v-for="item in assetCards" :key="item.key" class="asset-card" :class="[item.tone, `asset-${item.key}`]">
              <div class="asset-icon"><img :src="item.icon" alt=""></div>
              <div class="asset-main"><span>{{ item.name }}</span><strong>{{ item.value?.enabled_total ?? 0 }}</strong><small>已启用</small></div>
              <div v-if="item.value?.online_count !== undefined" class="online-summary">
                <div class="rate-ring" :style="{ '--rate': `${onlinePercent(item.value) * 3.6}deg` }"><span>{{ onlinePercent(item.value) }}%</span></div>
                <p><b>{{ item.value.online_count }}</b> 在线<br><small>{{ Math.max(0, item.value.enabled_total - item.value.online_count) }} 离线</small></p>
              </div>
              <div v-else class="enabled-state"><i></i>正常启用</div>
            </article>
          </div>
        </section>

        <section class="dashboard-section business-section">
          <header class="section-title"><div><h2>业务配置</h2><p>系统当前业务对象数量</p></div></header>
          <div class="business-grid" :class="{ skeleton: loading && !overview }">
            <article v-for="item in businessCards" :key="item.name" :class="item.tone">
              <span>{{ item.symbol }}</span><div><strong>{{ item.value }}</strong><small>{{ item.name }}</small></div>
            </article>
          </div>
        </section>
      </div>

      <section class="dashboard-section access-section">
        <header class="section-title">
          <div><h2>可访问功能</h2><p>根据当前账号的页面权限生成</p></div><span>{{ overview?.page.length ?? 0 }} 个页面</span>
        </header>
        <div v-if="overview?.page.length" class="access-list">
          <article v-for="item in overview.page" :key="item.key" :class="{ clickable: pageRoute(item) }" @click="openPage(item)">
            <div class="page-icon"><img :src="pageIcon(item.key)" alt=""></div>
            <div class="page-copy"><h3>{{ item.item }}</h3><p>{{ item.description }}</p><small>{{ item.usage }}</small></div>
            <button v-if="pageRoute(item)" title="进入页面">›</button>
          </article>
        </div>
        <div v-else-if="!loading" class="access-empty">当前账号暂无其他可访问页面</div>
        <div v-else class="access-empty">正在加载页面权限...</div>
      </section>
    </div>
  </main>
</template>

<style scoped>
.dashboard-page,.dashboard-page *{box-sizing:border-box}.dashboard-page{flex:1;min-width:0;height:100vh;padding:22px 28px;overflow:auto;background:#f3f6fb;color:#172033}.hero-card{position:relative;min-height:190px;display:flex;align-items:stretch;justify-content:space-between;gap:30px;padding:30px 34px;border-radius:20px;overflow:hidden;color:#fff;background:linear-gradient(120deg,#1e4f9d 0%,#2877d5 58%,#32a0df 100%);box-shadow:0 12px 32px rgba(29,92,172,.2)}.hero-card:before,.hero-card:after{content:'';position:absolute;border-radius:50%;border:1px solid rgba(255,255,255,.13)}.hero-card:before{width:330px;height:330px;right:-90px;top:-170px}.hero-card:after{width:220px;height:220px;right:125px;bottom:-180px}.hero-copy,.hero-summary{position:relative;z-index:1}.eyebrow{display:block;margin-bottom:12px;color:#c8e4ff;font-size:10px;font-weight:700;letter-spacing:1.8px}.hero-copy h1{margin:0 0 10px;font-size:27px;letter-spacing:.3px}.hero-copy p{max-width:650px;margin:0;color:#deefff;font-size:13px;line-height:1.7}.hero-meta{display:flex;gap:22px;margin-top:22px;color:#d8ebff;font-size:11px}.hero-meta span{display:flex;align-items:center;gap:7px}.pulse-dot{width:7px;height:7px;border-radius:50%;background:#77f0b0;box-shadow:0 0 0 5px rgba(119,240,176,.14)}.hero-summary{min-width:405px;display:grid;grid-template-columns:1fr 1fr;gap:1px;align-self:center;padding:15px;border:1px solid rgba(255,255,255,.2);border-radius:15px;background:rgba(255,255,255,.1);backdrop-filter:blur(8px)}.hero-summary>div{display:flex;flex-direction:column;padding:5px 18px}.hero-summary>div+div{border-left:1px solid rgba(255,255,255,.18)}.hero-summary strong{font-size:28px}.hero-summary div span{margin-top:3px;color:#d8ebff;font-size:10px}.hero-summary button{grid-column:1/-1;height:35px;margin-top:13px;border:1px solid rgba(255,255,255,.25);border-radius:8px;color:#fff;background:rgba(255,255,255,.12);cursor:pointer}.hero-summary button:hover{background:rgba(255,255,255,.2)}.hero-summary button span{display:inline-block;margin-right:6px;font-size:16px}.hero-summary button:disabled{cursor:wait;opacity:.75}.rotating{animation:rotate .8s linear infinite}@keyframes rotate{to{transform:rotate(360deg)}}.error-banner{display:flex;align-items:center;justify-content:space-between;margin-top:15px;padding:11px 14px;border:1px solid #fecaca;border-radius:10px;color:#b91c1c;background:#fff1f2;font-size:12px}.error-banner span{display:flex;align-items:center;gap:8px}.error-banner b{width:20px;height:20px;display:grid;place-items:center;border-radius:50%;color:#fff;background:#ef4444}.error-banner button{border:0;color:#2563eb;background:none;cursor:pointer}.dashboard-section{margin-top:18px;padding:20px;border:1px solid #e7edf5;border-radius:16px;background:#fff;box-shadow:0 4px 16px rgba(15,23,42,.045)}.section-title{display:flex;align-items:center;justify-content:space-between;margin-bottom:17px}.section-title h2{margin:0 0 4px;color:#172033;font-size:16px}.section-title p{margin:0;color:#94a3b8;font-size:10px}.section-title>span{padding:5px 10px;border-radius:12px;color:#55708e;background:#f1f5f9;font-size:10px}.asset-grid{display:grid;grid-template-columns:repeat(5,minmax(170px,1fr));gap:12px}.asset-card{position:relative;min-width:0;display:grid;grid-template-columns:42px minmax(60px,1fr);align-items:center;gap:11px;padding:17px 15px;border:1px solid #e8edf4;border-radius:13px;overflow:hidden;background:linear-gradient(145deg,#fff,#fbfdff)}.asset-card:before{content:'';position:absolute;inset:0 auto 0 0;width:3px;background:var(--tone)}.asset-card.blue{--tone:#3b82f6;--soft:#eaf2ff}.asset-card.cyan{--tone:#0891b2;--soft:#e5f8fb}.asset-card.violet{--tone:#7c3aed;--soft:#f1eafe}.asset-card.orange{--tone:#ea7b24;--soft:#fff1e6}.asset-card.green{--tone:#10a36c;--soft:#e6f8f1}.asset-icon{width:42px;height:42px;display:grid;place-items:center;border-radius:11px;background:var(--soft)}.asset-icon img{width:23px;height:23px;object-fit:contain;opacity:.72}.asset-main{display:grid;grid-template-columns:auto 1fr;align-items:baseline;column-gap:5px}.asset-main>span{grid-column:1/-1;margin-bottom:3px;color:#64748b;font-size:11px}.asset-main strong{color:#18233a;font-size:24px}.asset-main small{color:#a0aaba;font-size:9px}.online-summary,.enabled-state{grid-column:1/-1;margin-top:6px;padding-top:12px;border-top:1px solid #edf1f6}.online-summary{display:flex;align-items:center;gap:10px}.rate-ring{width:38px;height:38px;display:grid;place-items:center;border-radius:50%;background:conic-gradient(var(--tone) var(--rate),#edf1f5 0);position:relative}.rate-ring:after{content:'';position:absolute;inset:5px;border-radius:50%;background:#fff}.rate-ring span{position:relative;z-index:1;color:var(--tone);font-size:8px;font-weight:700}.online-summary p{margin:0;color:#64748b;font-size:9px;line-height:1.55}.online-summary p b{color:var(--tone);font-size:12px}.online-summary p small{font-size:9px}.enabled-state{display:flex;align-items:center;gap:7px;color:#7890aa;font-size:9px}.enabled-state i{width:7px;height:7px;border-radius:50%;background:var(--tone);box-shadow:0 0 0 4px var(--soft)}.lower-grid{display:grid;grid-template-columns:minmax(390px,.8fr) minmax(520px,1.2fr);gap:18px;padding-bottom:22px}.business-section,.access-section{min-width:0}.business-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.business-grid article{display:flex;align-items:center;gap:12px;padding:14px;border:1px solid #edf1f6;border-radius:11px;background:#fbfcfe}.business-grid article>span{width:34px;height:34px;display:grid;place-items:center;border-radius:9px;font-size:11px;font-weight:700}.business-grid article.blue>span{color:#2563eb;background:#dbeafe}.business-grid article.violet>span{color:#7c3aed;background:#ede9fe}.business-grid article.orange>span{color:#c65d0b;background:#ffedd5}.business-grid article.green>span{color:#05865a;background:#d1fae5}.business-grid article div{display:flex;flex-direction:column}.business-grid strong{color:#243149;font-size:20px}.business-grid small{margin-top:2px;color:#94a3b8;font-size:9px}.access-list{max-height:246px;display:flex;flex-direction:column;gap:8px;overflow:auto;padding-right:3px}.access-list article{display:grid;grid-template-columns:36px minmax(0,1fr) 28px;align-items:center;gap:11px;padding:11px 12px;border:1px solid #edf1f6;border-radius:10px;background:#fbfcfe;transition:.15s}.access-list article.clickable{cursor:pointer}.access-list article.clickable:hover{border-color:#bfdbfe;background:#f5f9ff;transform:translateX(2px)}.page-icon{width:36px;height:36px;display:grid;place-items:center;border-radius:9px;background:#355f9d}.page-icon img{width:18px;height:18px;object-fit:contain}.page-copy{min-width:0}.page-copy h3{margin:0 0 3px;color:#334155;font-size:12px}.page-copy p,.page-copy small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.page-copy p{margin:0;color:#718096;font-size:10px}.page-copy small{margin-top:3px;color:#a0aaba;font-size:9px}.access-list button{width:27px;height:27px;border:0;border-radius:7px;color:#397dec;background:#eaf2ff;font-size:20px;cursor:pointer}.access-empty{height:150px;display:grid;place-items:center;color:#94a3b8;font-size:12px}.skeleton{opacity:.55;filter:saturate(.6)}
/* 看板主体：左侧运行数据，右侧权限功能 */
.dashboard-layout{display:grid;grid-template-columns:minmax(0,1fr) 390px;align-items:stretch;gap:18px;padding-bottom:22px}.dashboard-left{min-width:0;display:flex;flex-direction:column;gap:18px}.dashboard-layout .dashboard-section{margin-top:18px}.dashboard-left .business-section{margin-top:0}.dashboard-layout .asset-grid{grid-template-columns:repeat(6,minmax(0,1fr));gap:14px}.dashboard-layout .asset-card{grid-column:span 2;min-height:150px;padding:20px 18px}.dashboard-layout .asset-terminal,.dashboard-layout .asset-sensor{grid-column:span 3;grid-template-columns:52px minmax(80px,1fr) auto;min-height:168px}.dashboard-layout .asset-icon{width:48px;height:48px;border-radius:13px}.dashboard-layout .asset-icon img{width:26px;height:26px}.dashboard-layout .asset-main>span{font-size:12px}.dashboard-layout .asset-main strong{font-size:29px}.dashboard-layout .online-summary{grid-column:3;grid-row:1;margin:0;padding:0 0 0 18px;border-top:0;border-left:1px solid #edf1f6}.dashboard-layout .rate-ring{width:64px;height:64px}.dashboard-layout .rate-ring:after{inset:7px}.dashboard-layout .rate-ring span{font-size:12px}.dashboard-layout .online-summary p{font-size:10px}.dashboard-layout .online-summary p b{font-size:15px}.dashboard-layout .enabled-state{margin-top:12px}.dashboard-layout .business-grid{grid-template-columns:repeat(4,minmax(0,1fr))}.dashboard-layout .business-grid article{padding:12px}.dashboard-layout .business-grid article>span{width:32px;height:32px}.dashboard-layout .access-section{min-width:0;display:flex;flex-direction:column}.dashboard-layout .access-list{max-height:none;flex:1;min-height:0}.dashboard-layout .access-list article{grid-template-columns:40px minmax(0,1fr) 28px;padding:14px 12px}.dashboard-layout .page-icon{width:40px;height:40px}.dashboard-layout .page-copy h3{font-size:13px}.dashboard-layout .page-copy p{margin-top:5px;line-height:1.5;white-space:normal}.dashboard-layout .page-copy small{margin-top:5px;line-height:1.5;white-space:normal}.dashboard-layout .access-empty{flex:1;min-height:300px}
.dashboard-layout .access-section{align-self:stretch;height:auto;min-height:0;overflow:hidden}.dashboard-layout .access-list{height:auto;max-height:none;flex:1 1 0;min-height:0;overflow-y:auto;scrollbar-width:thin;scrollbar-color:#cbd5e1 transparent}.dashboard-layout .access-list::-webkit-scrollbar{width:6px}.dashboard-layout .access-list::-webkit-scrollbar-track{background:transparent}.dashboard-layout .access-list::-webkit-scrollbar-thumb{border-radius:999px;background:#cbd5e1}.dashboard-layout .access-list::-webkit-scrollbar-thumb:hover{background:#94a3b8}
@media(max-width:1250px){.dashboard-layout{grid-template-columns:minmax(0,1fr) 340px}.dashboard-layout .business-grid{grid-template-columns:repeat(2,1fr)}.hero-summary{min-width:360px}}
@media(max-width:1100px){.dashboard-layout{grid-template-columns:1fr}.dashboard-layout .access-section{height:auto}.dashboard-layout .access-list{height:420px;max-height:420px;flex:none}.dashboard-layout .business-grid{grid-template-columns:repeat(4,1fr)}}
@media(max-width:850px){.dashboard-page{height:auto;min-height:100vh;padding:15px}.hero-card{flex-direction:column;padding:25px}.hero-summary{width:100%;min-width:0}.dashboard-layout .asset-grid{grid-template-columns:repeat(2,1fr)}.dashboard-layout .asset-card,.dashboard-layout .asset-terminal,.dashboard-layout .asset-sensor{grid-column:span 1;grid-template-columns:48px minmax(0,1fr)}.dashboard-layout .online-summary{grid-column:1/-1;grid-row:auto;padding:12px 0 0;border-top:1px solid #edf1f6;border-left:0}.dashboard-layout .business-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:560px){.dashboard-layout .asset-grid,.dashboard-layout .business-grid{grid-template-columns:1fr}.hero-summary{grid-template-columns:1fr}.hero-summary>div+div{border-left:0;border-top:1px solid rgba(255,255,255,.18)}.hero-meta{align-items:flex-start;flex-direction:column;gap:10px}}
</style>
