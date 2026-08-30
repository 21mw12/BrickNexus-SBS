// ==================== 权限判断 ====================

/**
 * 检查 page_codes 是否包含对某个 path_code 的访问权限。
 * - `"*"` 通配符表示拥有全部页面权限（root 账号）
 * - 支持层级前缀匹配：拥有 "user" 权限即可访问 "user:accounts"、"user:roles" 等子页面
 */
export function hasPagePermission(pageCodes: string[], targetPathCode: string): boolean {
  if (!pageCodes.length || !targetPathCode) return false
  return pageCodes.some(
    code => code === '*' || code === targetPathCode || targetPathCode.startsWith(code + ':'),
  )
}

// ==================== localStorage 存取 ====================

const STORAGE_KEY = 'auth_page_codes'

export function getStoredPageCodes(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    return JSON.parse(raw) as string[]
  } catch {
    return []
  }
}

export function storePageCodes(codes: string[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(codes))
}

export function clearPageCodes(): void {
  localStorage.removeItem(STORAGE_KEY)
}
