<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getCurrentUser, logout } from '../api/auth'
import { menuConfig, isMenuGroup, type MenuEntry, type MenuGroup } from '../config/menu'
import { getStoredPageCodes, hasPagePermission } from '../utils/permission'

const collapsed = ref(false)
const router = useRouter()
const route = useRoute()
const user = getCurrentUser() || { nickname: '游客' }

const nickname = computed(() => user.nickname || '游客')
const nicknameInitial = computed(() => (user.nickname ? user.nickname[0] : '游'))

// 当前用户拥有的 page_codes（登录时从 API 响应中获取并存储）
const pageCodes = getStoredPageCodes()

// 根据 page_codes 过滤菜单
// - "*" 通配符 → 显示全部（root 账号）
// - 空数组 → 显示全部（向后兼容：旧登录未存储权限）
// - 有具体值 → 按权限过滤
const permittedMenu = computed<MenuEntry[]>(() => {
  if (pageCodes.length === 0 || pageCodes.includes('*')) return menuConfig

  return menuConfig
    .map(entry => {
      if (isMenuGroup(entry)) {
        const permittedChildren = entry.children.filter(child =>
          hasPagePermission(pageCodes, child.path_code),
        )
        if (permittedChildren.length === 0) return null
        return { ...entry, children: permittedChildren }
      }
      if (!hasPagePermission(pageCodes, entry.path_code)) return null
      return entry
    })
    .filter(Boolean) as MenuEntry[]
})

// 默认折叠全部菜单组，由用户按需展开
const expandedGroups = ref<Set<string>>(new Set())

function toggleCollapsed() {
  collapsed.value = !collapsed.value
}

function toggleGroup(name: string) {
  const next = new Set(expandedGroups.value)
  if (next.has(name)) {
    next.delete(name)
  } else {
    next.add(name)
  }
  expandedGroups.value = next
}

function navigateTo(path: string) {
  router.push(path)
}

function isActive(entry: MenuEntry): boolean {
  if (isMenuGroup(entry)) {
    return entry.children.some(child => route.path === child.route)
  }
  return route.path === entry.route
}

function goProfile() {
  router.push('/profile')
}

async function handleLogout() {
  await logout()
  router.push('/login')
}
</script>

<template>
  <div class="home-layout">
    <aside :class="['sidebar', { collapsed }]">
      <div class="brand">
        <div class="brand-icon" @click="toggleCollapsed" title="展开/收起菜单">SB</div>
        <div class="brand-text" v-if="!collapsed">智慧楼宇</div>
      </div>

      <nav class="menu-list">
        <template v-for="entry in permittedMenu" :key="isMenuGroup(entry) ? entry.name : entry.route">
          <!-- 一级菜单项（直接路由） -->
          <button
            v-if="!isMenuGroup(entry)"
            :key="entry.route"
            class="menu-item"
            :class="{ active: isActive(entry) }"
            type="button"
            @click="navigateTo(entry.route)"
          >
            <img v-if="entry.icon" :src="entry.icon" class="menu-item-icon" alt="" />
            <span v-else-if="collapsed" class="menu-item-dot">{{ entry.name[0] }}</span>
            <span v-if="!collapsed">{{ entry.name }}</span>
          </button>

          <!-- 可折叠菜单组 -->
          <div v-else class="menu-group">
            <button
              class="menu-group-header"
              :class="{ active: isActive(entry) }"
              type="button"
              @click="collapsed ? navigateTo(entry.children[0]?.route || '') : toggleGroup(entry.name)"
            >
              <span class="menu-group-left">
                <img v-if="entry.icon" :src="entry.icon" class="menu-item-icon" alt="" />
                <span v-else-if="collapsed" class="menu-item-dot">{{ entry.name[0] }}</span>
                <span v-if="!collapsed" class="menu-group-name">{{ entry.name }}</span>
              </span>
              <img
                v-if="!collapsed"
                :src="expandedGroups.has(entry.name) ? '/icon/up_white.png' : '/icon/down_white.png'"
                class="group-arrow"
                alt=""
              />
            </button>
            <div v-show="expandedGroups.has(entry.name) && !collapsed" class="menu-group-children">
              <button
                v-for="child in entry.children"
                :key="child.route"
                class="menu-item sub-item"
                :class="{ active: route.path === child.route }"
                type="button"
                @click="navigateTo(child.route)"
              >
                <img v-if="child.icon" :src="child.icon" class="menu-item-icon" alt="" />
                <span>{{ child.name }}</span>
              </button>
            </div>
          </div>
        </template>
      </nav>

      <button class="collapse-toggle" @click="toggleCollapsed" :title="collapsed ? '展开菜单' : '收起菜单'">
        <img :src="collapsed ? '/icon/right_white.png' : '/icon/left_white.png'" alt="toggle" />
      </button>

      <div class="profile-card">
        <div class="profile-main" @click="goProfile" title="个人页面">
          <div class="avatar">{{ nicknameInitial }}</div>
          <div class="profile-info" v-if="!collapsed">
            <div class="profile-name">{{ nickname }}</div>
            <div class="profile-hint">个人页面</div>
          </div>
        </div>
        <button class="logout-icon" @click.stop="handleLogout" title="退出登录">
          <img src="/icon/logout_white.png" alt="退出登录" />
        </button>
      </div>
    </aside>

    <router-view />
  </div>
</template>

<style scoped>
.home-layout {
  display: flex;
  min-height: 100vh;
  background: #f2f5fb;
}

.sidebar {
  position: sticky;
  top: 0;
  width: 14%;
  min-width: 220px;
  height: 100vh;
  max-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #1f2937;
  color: #cbd5e1;
  padding: 24px 18px;
  box-sizing: border-box;
  overflow: hidden;
  transition: width 0.25s ease;
}

.sidebar.collapsed {
  width: 4%;
  min-width: 72px;
  padding-left: 12px;
  padding-right: 12px;
}

.brand {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  gap: 12px;
  margin-bottom: 32px;
}

.brand-icon {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: #3b82f6;
  font-weight: 800;
  color: #fff;
  cursor: pointer;
  transition: background 0.2s ease, transform 0.2s ease;
  user-select: none;
}

.brand-icon:hover {
  background: #2563eb;
  transform: scale(1.05);
}

.brand-text {
  font-size: 18px;
  font-weight: 700;
}

.menu-list {
  flex: 1;
  min-height: 0;
  margin-left: -18px;
  padding-left: 18px;
  overflow-x: hidden;
  overflow-y: auto;
  direction: rtl;
  scrollbar-width: thin;
  scrollbar-color: rgba(148, 163, 184, 0.38) transparent;
  overscroll-behavior: contain;
}

.menu-list > * {
  direction: ltr;
}

.sidebar.collapsed .menu-list {
  margin-left: -12px;
  padding-left: 12px;
}

.menu-list::-webkit-scrollbar {
  width: 5px;
}

.menu-list::-webkit-scrollbar-track {
  background: transparent;
}

.menu-list::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.38);
}

.menu-list::-webkit-scrollbar-thumb:hover {
  background: rgba(148, 163, 184, 0.58);
}

.menu-item {
  width: 100%;
  text-align: left;
  border: none;
  background: transparent;
  color: inherit;
  padding: 12px 14px;
  border-radius: 12px;
  cursor: pointer;
  transition: background 0.2s ease;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
}

.menu-item:hover {
  background: rgba(148, 163, 184, 0.14);
}

.menu-item.active {
  background: rgba(59, 130, 246, 0.2);
  color: #93c5fd;
}

.menu-item-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.menu-item-dot {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.12);
  display: grid;
  place-items: center;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
  color: #94a3b8;
}

.sub-item {
  font-size: 14px;
  padding-left: 28px;
}

/* 菜单组 */
.menu-group {
  margin-bottom: 4px;
}

.menu-group-header {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: none;
  background: transparent;
  color: inherit;
  padding: 12px 14px;
  border-radius: 12px;
  cursor: pointer;
  font-size: 15px;
  transition: background 0.2s ease;
}

.menu-group-header:hover {
  background: rgba(148, 163, 184, 0.14);
}

.menu-group-header.active {
  color: #93c5fd;
}

.menu-group-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.menu-group-name {
  text-align: left;
}

.group-arrow {
  width: 12px;
  height: 12px;
  opacity: 0.5;
  flex-shrink: 0;
  transition: opacity 0.2s ease;
}

.menu-group-header:hover .group-arrow {
  opacity: 0.8;
}

.menu-group-children {
  overflow: hidden;
}

.profile-card {
  margin-top: 18px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.05);
  transition: background 0.2s ease;
}

.profile-main {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
  cursor: pointer;
  border-radius: 10px;
  padding: 4px;
  transition: background 0.2s ease;
}

.profile-main:hover {
  background: rgba(255, 255, 255, 0.06);
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #2563eb;
  display: grid;
  place-items: center;
  font-weight: 700;
  color: #fff;
}

.profile-info {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.profile-name {
  font-size: 14px;
  font-weight: 600;
}

.profile-hint {
  font-size: 12px;
  color: #94a3b8;
}

.collapse-toggle {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translate(50%, -50%);
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 56px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 11px;
  background: #374151;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease;
  z-index: 10;
  padding: 0;
}

.collapse-toggle:hover {
  background: #4b5563;
  border-color: rgba(255, 255, 255, 0.25);
}

.collapse-toggle img {
  width: 12px;
  height: 12px;
  opacity: 0.7;
  transition: opacity 0.2s ease;
}

.collapse-toggle:hover img {
  opacity: 1;
}

.logout-icon {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border: none;
  border-radius: 10px;
  background: transparent;
  cursor: pointer;
  transition: background 0.2s ease;
  flex-shrink: 0;
}

.logout-icon img {
  width: 18px;
  height: 18px;
  opacity: 0.55;
  transition: opacity 0.2s ease, filter 0.2s ease;
}

.logout-icon:hover {
  background: rgba(239, 68, 68, 0.2);
}

.logout-icon:hover img {
  opacity: 1;
  filter: invert(30%) sepia(88%) saturate(4882%) hue-rotate(344deg) brightness(94%) contrast(108%);
}

/* collapsed: card stacks vertically, only avatar + logout */
.sidebar.collapsed .profile-card {
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 10px 6px;
}

.sidebar.collapsed .profile-main {
  padding: 0;
}

</style>
