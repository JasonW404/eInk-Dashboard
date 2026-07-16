import { useEffect, useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { api, type DisplayRevision, type HotspotSettings, type LatestReport, type SystemInfo, type Todo } from '../api/client'

type Route = '/' | '/todo' | '/settings'

const routes: Array<{ path: Route; label: string }> = [
  { path: '/', label: 'Overview' },
  { path: '/todo', label: 'Todo List' },
  { path: '/settings', label: 'Settings' },
]

function currentRoute(): Route {
  return routes.some(({ path }) => path === window.location.pathname)
    ? window.location.pathname as Route
    : '/'
}

export function App() {
  const [route, setRoute] = useState<Route>(currentRoute)

  useEffect(() => {
    const navigate = () => setRoute(currentRoute())
    window.addEventListener('popstate', navigate)
    return () => window.removeEventListener('popstate', navigate)
  }, [])

  const navigate = (next: Route) => {
    window.history.pushState({}, '', next)
    setRoute(next)
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Brand />
        <Navigation route={route} navigate={navigate} />
        <p className="sidebar-foot">RASPBERRY PI / 800×480</p>
      </aside>
      <main className="main-content">
        <header className="mobile-header"><Brand /></header>
        {route === '/' && <OverviewPage />}
        {route === '/todo' && <TodoPage />}
        {route === '/settings' && <SettingsPage />}
      </main>
      <nav className="mobile-nav" aria-label="Primary">
        <Navigation route={route} navigate={navigate} />
      </nav>
    </div>
  )
}

function Brand() {
  return (
    <div className="brand">
      <strong>INKPI</strong>
      <span>Ambient Productivity Terminal</span>
    </div>
  )
}

function Navigation({ route, navigate }: { route: Route; navigate: (route: Route) => void }) {
  return (
    <div className="nav-list">
      {routes.map((item) => (
        <button
          className={route === item.path ? 'nav-item active' : 'nav-item'}
          key={item.path}
          onClick={() => navigate(item.path)}
        >
          {item.label}
        </button>
      ))}
    </div>
  )
}

function OverviewPage() {
  const [todos, setTodos] = useState<Todo[]>([])
  const [revision, setRevision] = useState<DisplayRevision | null>(null)
  const [reports, setReports] = useState<LatestReport[]>([])
  const [online, setOnline] = useState(false)

  useEffect(() => {
    let active = true
    Promise.all([api.health(), api.todos(), api.revision(), api.latestReports()])
      .then(([, todoData, revisionData, reportData]) => {
        if (!active) return
        setOnline(true)
        setTodos(todoData)
        setRevision(revisionData)
        setReports(reportData)
      })
      .catch(() => active && setOnline(false))
    return () => { active = false }
  }, [])

  const visibleTodos = todos.filter((todo) => todo.display_on_eink).slice(0, 4)
  const codex = reports.find((report) => report.type === 'codex')?.payload
  const github = reports.find((report) => report.type === 'github')?.payload
  const weeklyUsed = codexWeeklyUsed(codex)
  const githubCommits = reportNumber(github, 'commits', 'user_monthly_commit_count')
  const githubPrs = reportNumber(github, 'prs', 'pull_requests')

  return (
    <Page title="Overview" eyebrow="DEVICE AT A GLANCE">
      <section className="overview-grid">
        <Panel title="Device Status" className="device-panel">
          <Status online={online} />
          <DefinitionList rows={[
            ['Device', 'InkPi'],
            ['API', online ? 'Connected' : 'Unavailable'],
            ['Version', 'v1.0-dev'],
          ]} />
        </Panel>
        <Panel title="Codex Usage">
          <p className="metric-label">WEEKLY USAGE</p>
          <p className="metric-value">{weeklyUsed === null ? '—' : `${weeklyUsed}%`}</p>
          <div className="progress"><span style={{ width: `${weeklyUsed ?? 0}%` }} /></div>
          <p className="muted">{codex ? `Plan ${String(codex.plan ?? '—')}` : 'Waiting for host agent report'}</p>
        </Panel>
        <Panel title="GitHub Activity">
          <p className="metric-label">THIS MONTH</p>
          <div className="split-metrics"><strong>{githubCommits ?? '—'}<small>COMMITS</small></strong><strong>{githubPrs ?? '—'}<small>PRS</small></strong></div>
          <p className="muted">{github ? 'Latest host agent report' : 'Waiting for host agent report'}</p>
        </Panel>
        <Panel title="Todo Summary" className="todo-summary-panel">
          <p className="metric-label">ON EINK</p>
          {visibleTodos.length === 0
            ? <p className="muted">No visible todos</p>
            : <ul className="summary-list">{visibleTodos.map((todo) => (
              <li key={todo.id} className={todo.completed ? 'done' : ''}>{todo.completed ? '■' : '□'} {todo.title}</li>
            ))}</ul>}
        </Panel>
      </section>
      <Panel title="eInk Preview" className="preview-panel">
        <div className="preview-frame">
          {revision ? (
            <img
              src={`/api/display/image?revision=${revision.revision}`}
              alt="Current 800 by 480 eInk output"
            />
          ) : (
            <span>DISPLAY PREVIEW UNAVAILABLE</span>
          )}
        </div>
        <div className="preview-meta">
          <span>REVISION #{revision?.revision ?? '—'}</span>
          <span>UPDATED {revision ? new Date(revision.updated_at).toLocaleString() : '—'}</span>
        </div>
      </Panel>
    </Page>
  )
}

function TodoPage() {
  const [todos, setTodos] = useState<Todo[]>([])
  const [title, setTitle] = useState('')
  const [error, setError] = useState('')

  const load = () => api.todos().then(setTodos).catch((reason: Error) => setError(reason.message))
  useEffect(() => { void load() }, [])

  const mutate = async (operation: () => Promise<unknown>) => {
    setError('')
    try {
      await operation()
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Request failed')
    }
  }

  const addTodo = async () => {
    const nextTitle = title.trim()
    if (!nextTitle) return
    await mutate(() => api.createTodo(nextTitle))
    setTitle('')
  }

  const move = (index: number, offset: number) => {
    const target = index + offset
    if (target < 0 || target >= todos.length) return
    const reordered = [...todos]
    ;[reordered[index], reordered[target]] = [reordered[target], reordered[index]]
    void mutate(() => api.reorderTodos(reordered.map((todo) => todo.id)))
  }

  return (
    <Page title="Todo List" eyebrow="PERSONAL QUEUE">
      <div className="todo-composer">
        <input value={title} onChange={(event) => setTitle(event.target.value)} onKeyDown={(event) => {
          if (event.key === 'Enter') void addTodo()
        }} placeholder="What needs to happen?" aria-label="New todo title" />
        <button className="primary-button" onClick={() => void addTodo()}>+ New Todo</button>
      </div>
      {error && <p className="error-message">{error}</p>}
      <section className="todo-list">
        {todos.length === 0 && <div className="empty-state">NO TODOS YET</div>}
        {todos.map((todo, index) => (
          <article className="todo-item" key={todo.id}>
            <button className="check-button" onClick={() => void mutate(() => api.updateTodo(todo.id, { completed: !todo.completed }))}>
              {todo.completed ? '■' : '□'}
            </button>
            <div className="todo-copy">
              <strong className={todo.completed ? 'done' : ''}>{todo.title}</strong>
              <span>CREATED {new Date(todo.created_at).toLocaleDateString()}</span>
            </div>
            <label className="eink-toggle">
              <input type="checkbox" checked={todo.display_on_eink} onChange={() => void mutate(() => api.updateTodo(todo.id, { display_on_eink: !todo.display_on_eink }))} />
              SHOW ON INKPI
            </label>
            <div className="todo-actions">
              <button disabled={index === 0} onClick={() => move(index, -1)}>↑</button>
              <button disabled={index === todos.length - 1} onClick={() => move(index, 1)}>↓</button>
              <button onClick={() => {
                const next = window.prompt('Edit todo', todo.title)?.trim()
                if (next && next !== todo.title) void mutate(() => api.updateTodo(todo.id, { title: next }))
              }}>EDIT</button>
              <button onClick={() => void mutate(() => api.deleteTodo(todo.id))}>DELETE</button>
            </div>
          </article>
        ))}
      </section>
    </Page>
  )
}

function SettingsPage() {
  const [network, setNetwork] = useState<HotspotSettings | null>(null)
  const [system, setSystem] = useState<SystemInfo | null>(null)
  const [ssid, setSsid] = useState('InkPi-AP')
  const [password, setPassword] = useState('')
  const [adminToken, setAdminToken] = useState('')
  const [showQr, setShowQr] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    Promise.all([api.networkSettings(), api.systemSettings()])
      .then(([settings, systemInfo]) => {
        setNetwork(settings)
        setSystem(systemInfo)
        setSsid(settings.ssid)
      })
      .catch((reason: Error) => setMessage(reason.message))
  }, [])

  const save = async (enabled: boolean) => {
    setMessage('')
    setShowQr(false)
    if (!adminToken.trim()) {
      setMessage('Admin token is required for network changes.')
      return
    }
    if (enabled && password.length < 8) {
      setMessage('Enter the current or new hotspot password (at least 8 characters).')
      return
    }
    setSaving(true)
    try {
      const updated = await api.updateHotspot(
        { enabled, ssid: ssid.trim(), ...(enabled ? { password } : {}) },
        adminToken.trim(),
      )
      setNetwork(updated)
      setSsid(updated.ssid)
      setMessage(enabled ? 'Hotspot configuration applied.' : 'Hotspot disabled.')
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : 'Network request failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Page title="Settings" eyebrow="DEVICE CONFIGURATION">
      <div className="settings-stack">
        <Panel title="Device">
          <DefinitionList rows={[["Name", system?.device_name ?? '—'], ["Timezone", Intl.DateTimeFormat().resolvedOptions().timeZone], ["Firmware", system?.firmware_version ?? '—']]} />
        </Panel>
        <Panel title="Network">
          <h3 className="settings-subheading">WiFi Hotspot</h3>
          <div className="network-status-row">
            <Status online={network?.enabled ?? false} />
            <span>{network?.enabled ? 'HOTSPOT ON' : 'HOTSPOT OFF'}</span>
          </div>
          <div className="settings-form">
            <label>SSID<input value={ssid} maxLength={32} onChange={(event) => setSsid(event.target.value)} /></label>
            <label>Password<input type="password" value={password} minLength={8} maxLength={63} autoComplete="new-password" onChange={(event) => {
              setPassword(event.target.value)
              setShowQr(false)
            }} placeholder="Not stored by InkPi" /></label>
            <label>Admin token<input type="password" value={adminToken} autoComplete="off" onChange={(event) => setAdminToken(event.target.value)} placeholder="INKPI_ADMIN_TOKEN" /></label>
          </div>
          <DefinitionList rows={[["Connected devices", String(network?.connected_clients ?? '—')], ["Updated", network ? new Date(network.updated_at).toLocaleString() : '—']]} />
          <div className="settings-actions">
            <button className="primary-button" disabled={saving || !ssid.trim()} onClick={() => void save(true)}>{network?.enabled ? 'Apply & Restart' : 'Enable Hotspot'}</button>
            <button disabled={saving || !network?.enabled} onClick={() => void save(false)}>Disable</button>
            <button disabled={!password || !ssid.trim()} onClick={() => setShowQr((value) => !value)}>Generate QR Code</button>
          </div>
          {message && <p className="settings-message" role="status">{message}</p>}
          {showQr && password && <div className="wifi-qr"><QRCodeSVG value={wifiQrValue(ssid, password)} size={180} level="M" marginSize={2} title={`Connect to ${ssid}`} /><p>Scan to join {ssid}</p></div>}
          <p className="muted">The password stays only in this browser field and the current privileged-helper request. InkPi never returns or stores it.</p>
        </Panel>
        <Panel title="Display Information">
          <DefinitionList rows={[["Resolution", "800 × 480"], ["Last refresh", system?.last_refresh ? new Date(system.last_refresh).toLocaleString() : 'Not reported'], ["Current revision", String(system?.display_revision ?? '—')], ["Device uptime", formatUptime(system?.uptime_seconds)]]} />
          <p className="muted">Refresh interval, partial count, and full-refresh policy remain private to the display service.</p>
        </Panel>
      </div>
    </Page>
  )
}

function wifiQrValue(ssid: string, password: string): string {
  const escape = (value: string) => value.replace(/([\\;,:"])/g, '\\$1')
  return `WIFI:T:WPA;S:${escape(ssid)};P:${escape(password)};;`
}

function formatUptime(seconds: number | undefined): string {
  if (seconds === undefined) return '—'
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  return `${days}d ${hours}h ${minutes}m`
}

function Page({ title, eyebrow, children }: { title: string; eyebrow: string; children: React.ReactNode }) {
  return <><div className="page-heading"><span>{eyebrow}</span><h1>{title}</h1></div>{children}</>
}

function Panel({ title, children, className = '' }: { title: string; children: React.ReactNode; className?: string }) {
  return <section className={`panel ${className}`}><h2>{title}</h2><div className="panel-body">{children}</div></section>
}

function Status({ online }: { online: boolean }) {
  return <div className={online ? 'status online' : 'status error'}><span />{online ? 'ONLINE' : 'OFFLINE'}</div>
}

function DefinitionList({ rows }: { rows: string[][] }) {
  return <dl>{rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
}

function reportNumber(
  payload: Record<string, unknown> | undefined,
  ...keys: string[]
): number | null {
  if (!payload) return null
  for (const key of keys) {
    const value = payload[key]
    if (typeof value === 'number' && Number.isFinite(value)) return value
  }
  return null
}

function codexWeeklyUsed(payload: Record<string, unknown> | undefined): number | null {
  const direct = reportNumber(payload, 'weekly_used_percent')
  if (direct !== null) return Math.round(direct)
  const windows = payload?.windows
  if (!Array.isArray(windows)) return null
  const weekly = windows.find((window) => (
    typeof window === 'object' && window !== null && String((window as Record<string, unknown>).label).includes('WEEKLY')
  )) as Record<string, unknown> | undefined
  const remaining = weekly?.remaining_percent
  return typeof remaining === 'number' ? Math.round(100 - remaining) : null
}
