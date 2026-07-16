export interface Todo {
  id: number
  title: string
  completed: boolean
  display_on_eink: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

export interface DisplayRevision {
  revision: number
  updated_at: string
}

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
  connected_clients: number
  updated_at: string
  operation: Record<string, unknown> | null
}

export interface SystemInfo {
  device_name: string
  firmware_version: string
  uptime_seconds: number
  display_revision: number
  last_refresh: string | null
}

export interface AuthSession {
  authenticated: boolean
  csrf_token: string | null
}

let csrfToken: string | null = null

type TodoChanges = Partial<Pick<Todo, 'title' | 'completed' | 'display_on_eink'>>

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
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
  revision: () => request<DisplayRevision>('/api/display/revision'),
  displayContext: () => request<DisplayContext>('/api/display/context'),
  latestReports: () => request<LatestReport[]>('/api/reports/latest'),
  networkSettings: () => request<HotspotSettings>('/api/settings/network'),
  hotspotCredentials: () => request<{ password: string }>('/api/settings/network/hotspot/credentials'),
  systemSettings: () => request<SystemInfo>('/api/settings/system'),
  updateHotspot: (
    changes: { enabled: boolean; ssid: string; password?: string },
  ) => request<HotspotSettings>('/api/settings/network/hotspot', {
    method: 'PUT',
    headers: csrfToken ? { 'X-CSRF-Token': csrfToken } : undefined,
    body: JSON.stringify(changes),
  }),
  createTodo: (title: string) => request<Todo>('/api/todos', {
    method: 'POST',
    body: JSON.stringify({ title }),
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
