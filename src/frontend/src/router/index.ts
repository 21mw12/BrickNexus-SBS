import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import MainLayout from '../views/MainLayout.vue'
import ProfileView from '../views/ProfileView.vue'
import { buildRouteCodeMap, getFirstPermittedRoute } from '../config/menu'
import { getStoredPageCodes, hasPagePermission } from '../utils/permission'
import { isTokenExpired, redirectToLogin } from '../utils/authSession'

import HomePageView from '../views/subpages/HomePageView.vue'
import UserAccountPageView from '../views/subpages/UserAccountPageView.vue'
import UserRolePageView from '../views/subpages/UserRolePageView.vue'
import AssetTreePageView from '../views/subpages/AssetTreePageView.vue'
import AssetTablePageView from '../views/subpages/AssetTablePageView.vue'
import SensorModelPageView from '../views/subpages/SensorModelPageView.vue'
import FloorPlanPageView from '../views/subpages/FloorPlanPageView.vue'
import RealtimeDataPageView from '../views/subpages/RealtimeDataPageView.vue'
import HistoryDataPageView from '../views/subpages/HistoryDataPageView.vue'
import ChannelRequestsPageView from '../views/subpages/ChannelRequestsPageView.vue'
import ChannelManagementPageView from '../views/subpages/ChannelManagementPageView.vue'
import ChannelControlsPageView from '../views/subpages/ChannelControlsPageView.vue'
import RulesPageView from '../views/subpages/RulesPageView.vue'
import LogsPageView from '../views/subpages/LogsPageView.vue'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: LoginView,
  },
  {
    path: '/',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/dashboard',
      },
      {
        path: 'profile',
        name: 'Profile',
        component: ProfileView,
      },

      // 看板 相关页面
      {
        path: 'dashboard',
        name: 'DashBoard',
        component: HomePageView,
      },

      // 楼层平面图配置 相关页面
      {
        path: 'floorPlan',
        name: 'FloorPlan',
        component: FloorPlanPageView,
      },

      // 资产中心 相关页面
      {
        path: 'asset/tree',
        name: 'AssetTree',
        component: AssetTreePageView,
      },
      {
        path: 'asset/table',
        name: 'AssetTable',
        component: AssetTablePageView,
      },
      {
        path: 'asset/model',
        name: 'SensorModel',
        component: SensorModelPageView,
      },

      // 数据监测 相关页面
      {
        path: 'data/realtime',
        name: 'DataRealtime',
        component: RealtimeDataPageView,
      },
      {
        path: '/data/history',
        name: 'DataHistory',
        component: HistoryDataPageView,
      },

      // 采控通道配置 相关页面
      {
        path: 'channel/management',
        name: 'ChannelManagement',
        component: ChannelManagementPageView,
      },
      {
        path: 'channel/requests',
        name: 'ChannelRequests',
        component: ChannelRequestsPageView,
      },
      {
        path: 'channel/controls',
        name: 'ChannelControls',
        component: ChannelControlsPageView,
      },

      // 规则管理 相关页面
      {
        path: 'rules',
        name: 'Rules',
        component: RulesPageView,
      },

      // 用户管理 相关页面
      {
        path: 'user/account',
        name: 'Account',
        component: UserAccountPageView,
      },
      {
        path: 'user/role',
        name: 'Role',
        component: UserRolePageView,
      },

      // 系统日志
      {
        path: 'logs',
        name: 'Logs',
        component: LogsPageView,
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 构建 路由 → path_code 映射表（仅需一次）
const routeCodeMap = buildRouteCodeMap()

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('auth_token')

  if (token && isTokenExpired(token)) {
    redirectToLogin()
    return next(false)
  }

  // 1. 需要登录的页面，未登录则跳转登录
  if (to.meta.requiresAuth && !token) {
    return next('/login')
  }

  // 2. 已登录用户访问登录页，重定向到第一个有权限的页面
  if (to.path === '/login' && token) {
    return next('/dashboard')
  }

  // 3. 页面权限检查：仅对菜单中配置了 path_code 的路由进行校验
  if (token && to.meta.requiresAuth) {
    const pathCode = routeCodeMap.get(to.path)
    if (pathCode) {
      const pageCodes = getStoredPageCodes()
      // pageCodes 为空（向后兼容）或含 "*"（root）→ 不限制
      if (pageCodes.length > 0 && !pageCodes.includes('*') && !hasPagePermission(pageCodes, pathCode)) {
        // 无权限 → 重定向到第一个有权限的页面
        return next(getFirstPermittedRoute(pageCodes, hasPagePermission))
      }
    }
  }

  next()
})

export default router
