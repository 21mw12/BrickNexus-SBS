export interface MenuItem {
  icon?: string   // 图标路径，非必须
  name: string
  route: string
  path_code: string  // 对应后端的页面 path_code，用于权限匹配
}

export interface MenuGroup {
  icon?: string
  name: string
  children: MenuItem[]
}

export type MenuEntry = MenuItem | MenuGroup

export function isMenuGroup(entry: MenuEntry): entry is MenuGroup {
  return 'children' in entry
}

export const menuConfig: MenuEntry[] = [
  {
    icon: '/icon/page_dashboard_white.png',
    name: '看板',
    route: '/dashboard',
    path_code: 'dashboard',
  },
  {
    icon: '/icon/page_floorplan_white.png',
    name: '楼层平面图配置',
    route: '/floorPlan',
    path_code: 'floorPlan',
  },
  {
    icon: '/icon/page_asset_white.png',
    name: '资产中心',
    children: [
      { name: '资产树', route: '/asset/tree', path_code: 'asset:tree' },
      { name: '资产表', route: '/asset/table', path_code: 'asset:table' },
      { name: '型号与测点', route: '/asset/model', path_code: 'asset:model' },
    ],
  },
  {
    icon: '/icon/page_data_white.png',
    name: '数据监测',
    children: [
      { name: '实时数据', route: '/data/realtime', path_code: 'data:realtime' },
      { name: '历史数据', route: '/data/history', path_code: 'data:history' },
    ],
  },
  {
    icon: '/icon/page_channel_white.png',
    name: '采控通道配置',
    children: [
      { name: '通道管理', route: '/channel/management', path_code: 'channel:management' },
      { name: '请求管理', route: '/channel/requests', path_code: 'channel:requests' },
      { name: '控制管理', route: '/channel/controls', path_code: 'channel:controls' },
    ],
  },
  {
    icon: '/icon/page_rules_white.png',
    name: '规则管理',
    route: '/rules',
    path_code: 'rules',
  },
  {
    icon: '/icon/page_user_white.png',
    name: '用户管理',
    children: [
      { name: '账户管理', route: '/user/account', path_code: 'user:accounts' },
      { name: '角色管理', route: '/user/role', path_code: 'user:roles' },
    ],
  },
  {
    icon: '/icon/page_logs_white.png',
    name: '系统日志',
    route: '/logs',
    path_code: 'logs',
  },
]

/**
 * 从菜单配置中构建 路由 → path_code 的映射表（供路由守卫使用）
 */
export function buildRouteCodeMap(): Map<string, string> {
  const map = new Map<string, string>()
  for (const entry of menuConfig) {
    if (isMenuGroup(entry)) {
      for (const child of entry.children) {
        map.set(child.route, child.path_code)
      }
    } else {
      map.set(entry.route, entry.path_code)
    }
  }
  return map
}

/**
 * 按菜单顺序返回第一个用户有权访问的路由。
 * pageCodes 为空或含 "*" 时返回看板。
 */
export function getFirstPermittedRoute(pageCodes: string[], hasPermission: (codes: string[], code: string) => boolean): string {
  if (pageCodes.length === 0 || pageCodes.includes('*')) return '/dashboard'

  for (const entry of menuConfig) {
    if (isMenuGroup(entry)) {
      for (const child of entry.children) {
        if (hasPermission(pageCodes, child.path_code)) return child.route
      }
    } else {
      if (hasPermission(pageCodes, entry.path_code)) return entry.route
    }
  }

  // 所有页面都无权限时也返回 /home（极端情况）
  return '/dashboard'
}
