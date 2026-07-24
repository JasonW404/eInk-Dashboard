export interface Todo {
  id: number
  parent_id: number | null
  title: string
  completed: boolean
  display_on_eink: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

export interface DisplayRevision {
  revision: string
  updated_at: string
}

export type TodoSort = 'manual' | 'created_asc' | 'created_desc' | 'completed_asc' | 'completed_desc'
export interface TodoDisplaySettings { show_completed: boolean; sort: TodoSort }

export interface DisplayContext {
  hotspot_enabled: boolean
  hotspot_ssid: string | null
  wifi_qr_payload: string | null
}

export interface LatestReport {
  id: number
  agent_id: number
  agent_name: string
  type: string
  payload: Record<string, unknown>
  created_at: string
  expires_at: string | null
}

export interface HotspotSettings {
  enabled: boolean
  ssid: string
  security: HotspotSecurity
  connected_clients: number
  updated_at: string
  operation: Record<string, unknown> | null
}

export type HotspotSecurity = 'open' | 'wpa2' | 'wpa3' | 'wpa2-wpa3'

export interface DisplayPage {
  id: number
  kind: 'dashboard' | 'photo' | 'text'
  content: string | null
  name: string
  sort_order: number
  interval_seconds: number
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface SystemInfo {
  device_name: string
  firmware_version: string
  uptime_seconds: number
  display_revision: string
  last_refresh: string | null
}

export interface AuthSession {
  authenticated: boolean
  csrf_token: string | null
}

let csrfToken: string | null = null

export function apiPath(path: string, pathname = window.location.pathname): string {
  const base = pathname === '/inkpi' || pathname.startsWith('/inkpi/') ? '/inkpi' : ''
  return `${base}${path}`
}

type TodoChanges = Partial<Pick<Todo, 'title' | 'completed' | 'display_on_eink'>>

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiPath(path), {
    ...init,
    headers: init?.body ? { 'Content-Type': 'application/json', ...init.headers } : init?.headers,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(body?.detail ?? `Request failed (${response.status})`)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

async function uploadRequest<T>(path: string, file: File): Promise<T> {
  const response = await fetch(apiPath(path), {
    method: 'POST', body: file,
    headers: { ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}), 'X-File-Name': file.name },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(body?.detail ?? `Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}

export const api = {
  login: async (token: string, remember: boolean) => {
    const session = await request<AuthSession>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ token, remember }),
    })
    csrfToken = session.csrf_token
    return session
  },
  session: async () => {
    const session = await request<AuthSession>('/api/auth/session')
    csrfToken = session.csrf_token
    return session
  },
  logout: async () => {
    await request<void>('/api/auth/logout', { method: 'POST' })
    csrfToken = null
  },
  health: () => request<{ status: string }>('/api/health'),
  todos: () => request<Todo[]>('/api/todos'),
  todoDisplaySettings: () => request<TodoDisplaySettings>('/api/settings/todos/display'),
  updateTodoDisplaySettings: (settings: TodoDisplaySettings) => request<TodoDisplaySettings>('/api/settings/todos/display', {
    method: 'PUT', body: JSON.stringify(settings),
  }),
  revision: () => request<DisplayRevision>('/api/display/revision'),
  displayContext: () => request<DisplayContext>('/api/display/context'),
  latestReports: () => request<LatestReport[]>('/api/reports/latest'),
  networkSettings: () => request<HotspotSettings>('/api/settings/network'),
  hotspotCredentials: () => request<{ password: string | null }>('/api/settings/network/hotspot/credentials'),
  systemSettings: () => request<SystemInfo>('/api/settings/system'),
  updateHotspot: (
    changes: { enabled: boolean; ssid: string; security: HotspotSecurity; password?: string },
  ) => request<HotspotSettings>('/api/settings/network/hotspot', {
    method: 'PUT',
    headers: csrfToken ? { 'X-CSRF-Token': csrfToken } : undefined,
    body: JSON.stringify(changes),
  }),
  pages: () => request<DisplayPage[]>('/api/pages'),
  pageImage: (id: number, updatedAt: string) => `${apiPath(`/api/pages/${id}/image`)}?v=${encodeURIComponent(updatedAt)}`,
  uploadPage: (file: File) => uploadRequest<DisplayPage>('/api/pages', file),
  createTextPage: (name: string, content: string) => request<DisplayPage>('/api/pages/text', {
    method: 'POST', headers: csrfToken ? { 'X-CSRF-Token': csrfToken } : undefined,
    body: JSON.stringify({ name, content }),
  }),
  updatePage: (id: number, changes: Partial<Pick<DisplayPage, 'name' | 'interval_seconds' | 'enabled' | 'content'>>) => request<DisplayPage>(`/api/pages/${id}`, {
    method: 'PATCH', headers: csrfToken ? { 'X-CSRF-Token': csrfToken } : undefined, body: JSON.stringify(changes),
  }),
  deletePage: (id: number) => request<void>(`/api/pages/${id}`, { method: 'DELETE', headers: csrfToken ? { 'X-CSRF-Token': csrfToken } : undefined }),
  reorderPages: (orderedIds: number[]) => request<DisplayPage[]>('/api/pages/order', {
    method: 'PUT', headers: csrfToken ? { 'X-CSRF-Token': csrfToken } : undefined, body: JSON.stringify({ ordered_ids: orderedIds }),
  }),
  createTodo: (title: string, parentId: number | null = null) => request<Todo>('/api/todos', {
    method: 'POST',
    body: JSON.stringify({ title, parent_id: parentId }),
  }),
  updateTodo: (id: number, changes: TodoChanges) => request<Todo>(`/api/todos/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(changes),
  }),
  deleteTodo: (id: number) => request<void>(`/api/todos/${id}`, { method: 'DELETE' }),
  reorderTodos: (orderedIds: number[]) => request<Todo[]>('/api/todos/order', {
    method: 'PUT',
    body: JSON.stringify({ ordered_ids: orderedIds }),
  }),
}
