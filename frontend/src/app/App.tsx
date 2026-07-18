import { useEffect, useRef, useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { api, apiPath, type DisplayPage, type DisplayRevision, type HotspotSecurity, type HotspotSettings, type LatestReport, type SystemInfo, type Todo } from '../api/client'
import { appPath, routeFromPathname, type AppRoute } from './basePath'

type Route = AppRoute

const routes: Array<{ path: Route; label: string }> = [
  { path: '/', label: 'Overview' },
  { path: '/todo', label: 'Todo List' },
  { path: '/pages', label: 'Pages' },
  { path: '/settings', label: 'Settings' },
]

function currentRoute(): Route {
  return routeFromPathname(window.location.pathname)
}

export function App() {
  const [route, setRoute] = useState<Route>(currentRoute)
  const [authenticated, setAuthenticated] = useState<boolean | null>(null)

  useEffect(() => {
    const navigate = () => setRoute(currentRoute())
    window.addEventListener('popstate', navigate)
    return () => window.removeEventListener('popstate', navigate)
  }, [])

  useEffect(() => {
    api.session().then((session) => setAuthenticated(session.authenticated)).catch(() => setAuthenticated(false))
  }, [])

  const navigate = (next: Route) => {
    window.history.pushState({}, '', appPath(next))
    setRoute(next)
  }

  if (authenticated === null) return <div className="auth-loading">INKPI</div>
  if (!authenticated) return <LoginPage onLogin={() => setAuthenticated(true)} />

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Brand />
        <Navigation route={route} navigate={navigate} />
        <button className="logout-button" onClick={() => void api.logout().then(() => setAuthenticated(false))}>LOG OUT</button>
        <p className="sidebar-foot">RASPBERRY PI / 800×480</p>
      </aside>
      <main className="main-content">
        <header className="mobile-header"><Brand /></header>
        {route === '/' && <OverviewPage />}
        {route === '/todo' && <TodoPage />}
        {route === '/pages' && <PagesPage />}
        {route === '/settings' && <SettingsPage />}
      </main>
      <nav className="mobile-nav" aria-label="Primary">
        <Navigation route={route} navigate={navigate} />
      </nav>
    </div>
  )
}

function LoginPage({ onLogin }: { onLogin: () => void }) {
  const [token, setToken] = useState('')
  const [remember, setRemember] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const login = async () => {
    if (!token) return
    setLoading(true)
    setError('')
    try {
      await api.login(token, remember)
      onLogin()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="login-page">
      <form className="login-card" onSubmit={(event) => { event.preventDefault(); void login() }}>
        <Brand />
        <div><p className="eyebrow">DEVICE ADMINISTRATION</p><h1>Sign in to InkPi</h1></div>
        <label>Admin token<input type="password" value={token} autoFocus autoComplete="current-password" onChange={(event) => setToken(event.target.value)} /></label>
        <label className="remember-login"><input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} /> Remember login</label>
        <button className="primary-button" disabled={loading || !token}>{loading ? 'SIGNING IN…' : 'SIGN IN'}</button>
        {error && <p className="error-message" role="alert">{error}</p>}
      </form>
    </main>
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
          <WebContributionCalendar payload={github} />
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
              src={`${apiPath('/api/display/image')}?revision=${revision.revision}`}
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

function WebContributionCalendar({ payload }: { payload: Record<string, unknown> | undefined }) {
  const counts = new Map<string, number>()
  const contributions = payload?.contributions
  if (Array.isArray(contributions)) contributions.forEach((item) => {
    if (typeof item !== 'object' || item === null) return
    const row = item as Record<string, unknown>
    if (typeof row.day === 'string' && typeof row.commit_count === 'number') counts.set(row.day, row.commit_count)
  })
  const today = new Date()
  const first = new Date(today.getFullYear(), today.getMonth(), 1)
  const days = new Date(today.getFullYear(), today.getMonth() + 1, 0).getDate()
  const cells: Array<{ key: string; count: number } | null> = Array(first.getDay()).fill(null)
  for (let day = 1; day <= days; day += 1) {
    const key = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
    cells.push({ key, count: counts.get(key) ?? 0 })
  }
  return <div className="web-calendar" aria-label="Current month GitHub contributions">{cells.map((cell, index) => cell
    ? <i key={cell.key} className={cell.count === 0 ? '' : cell.count < 4 ? 'low' : 'high'} title={`${cell.key}: ${cell.count} contributions`} />
    : <i key={`blank-${index}`} className="blank" />)}</div>
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

function PagesPage() {
  const [pages, setPages] = useState<DisplayPage[]>([])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [cropQueue, setCropQueue] = useState<File[]>([])
  const load = () => api.pages().then(setPages).catch((reason: Error) => setMessage(reason.message))
  useEffect(() => { void load() }, [])
  const mutate = async (operation: () => Promise<unknown>) => {
    setBusy(true); setMessage('')
    try { await operation(); await load(); return true } catch (reason) { setMessage(reason instanceof Error ? reason.message : 'Request failed'); return false } finally { setBusy(false) }
  }
  const move = (index: number, offset: number) => {
    const target = index + offset
    if (target < 0 || target >= pages.length) return
    const next = [...pages]; [next[index], next[target]] = [next[target], next[index]]
    void mutate(() => api.reorderPages(next.map((page) => page.id)))
  }
  return <Page title="Pages" eyebrow="DISPLAY PLAYLIST">
    <section className="page-toolbar">
      <div><strong>Display playlist</strong><span>Arrange the dashboard and photos in one continuous loop</span></div>
      <label className="upload-button">+ Upload photos<input disabled={busy} type="file" accept="image/*" multiple onChange={(event) => {
        const files = Array.from(event.target.files ?? [])
        if (files.length) setCropQueue(files)
        event.target.value = ''
      }} /></label>
    </section>
    {message && <p className="settings-message" role="status">{message}</p>}
    <div className="pages-list">
      {pages.length === 0 && <div className="empty-state">UPLOAD PHOTOS TO EXTEND THE DISPLAY LOOP</div>}
      {pages.map((page, index) => <article className="page-row" key={page.id}>
        <div className="page-order"><button disabled={busy || index === 0} onClick={() => move(index, -1)}>↑</button><button disabled={busy || index === pages.length - 1} onClick={() => move(index, 1)}>↓</button></div>
        <div className="page-copy"><strong>{page.name}</strong><span>{page.kind === 'dashboard' ? 'LIVE INKPI OVERVIEW' : `PHOTO PAGE · POSITION ${index + 1}`}</span></div>
        <label>Interval<select value={page.interval_seconds} disabled={busy} onChange={(event) => void mutate(() => api.updatePage(page.id, { interval_seconds: Number(event.target.value) }))}><option value={30}>30 sec</option><option value={60}>1 min</option><option value={300}>5 min</option><option value={900}>15 min</option><option value={3600}>1 hour</option></select></label>
        <label className="page-enabled"><input type="checkbox" checked={page.enabled} disabled={busy || page.kind === 'dashboard'} onChange={() => void mutate(() => api.updatePage(page.id, { enabled: !page.enabled }))} /> ACTIVE</label>
        <button className="delete-page" disabled={busy || page.kind === 'dashboard'} onClick={() => void mutate(() => api.deletePage(page.id))}>{page.kind === 'dashboard' ? 'BUILT IN' : 'DELETE'}</button>
      </article>)}
    </div>
    <p className="muted">Active pages cycle in this order. Photos are cropped to the 800 × 480 display ratio without stretching; each page's interval controls when the physical display advances.</p>
    {cropQueue[0] && <ImageCropDialog file={cropQueue[0]} queueLength={cropQueue.length} onCancel={() => setCropQueue([])} onConfirm={async (cropped) => {
      const uploaded = await mutate(() => api.uploadPage(cropped))
      if (uploaded) setCropQueue((queue) => queue.slice(1))
      return uploaded
    }} />}
  </Page>
}

function ImageCropDialog({ file, queueLength, onCancel, onConfirm }: { file: File; queueLength: number; onCancel: () => void; onConfirm: (file: File) => Promise<boolean> }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const dragRef = useRef<{ x: number; y: number; positionX: number; positionY: number } | null>(null)
  const [image, setImage] = useState<HTMLImageElement | null>(null)
  const [positionX, setPositionX] = useState(50)
  const [positionY, setPositionY] = useState(50)
  const [zoom, setZoom] = useState(1)
  const [processing, setProcessing] = useState(false)

  useEffect(() => {
    setPositionX(50)
    setPositionY(50)
    setZoom(1)
    setImage(null)
    const url = URL.createObjectURL(file)
    const nextImage = new Image()
    nextImage.onload = () => setImage(nextImage)
    nextImage.src = url
    return () => URL.revokeObjectURL(url)
  }, [file])

  useEffect(() => {
    if (!image || !canvasRef.current) return
    drawCroppedImage(canvasRef.current, image, positionX / 100, positionY / 100, zoom)
  }, [image, positionX, positionY, zoom])

  const confirm = () => {
    const canvas = canvasRef.current
    if (!canvas) return
    setProcessing(true)
    canvas.toBlob(async (blob) => {
      if (!blob) { setProcessing(false); return }
      const baseName = file.name.replace(/\.[^.]+$/, '') || 'Photo'
      await onConfirm(new File([blob], `${baseName}.png`, { type: 'image/png' }))
      setProcessing(false)
    }, 'image/png', 1)
  }

  return <div className="crop-backdrop" role="presentation">
    <section className="crop-dialog" role="dialog" aria-modal="true" aria-labelledby="crop-title">
      <header><div><span className="eyebrow">PHOTO {queueLength > 1 ? `· ${queueLength} REMAINING` : ''}</span><h2 id="crop-title">Crop for InkPi</h2></div><button onClick={onCancel} aria-label="Cancel cropping">×</button></header>
      <div className="crop-stage"><canvas ref={canvasRef} width={800} height={480} aria-label="Cropped photo preview" onPointerDown={(event) => {
        event.currentTarget.setPointerCapture(event.pointerId)
        dragRef.current = { x: event.clientX, y: event.clientY, positionX, positionY }
      }} onPointerMove={(event) => {
        const drag = dragRef.current
        if (!drag) return
        const bounds = event.currentTarget.getBoundingClientRect()
        setPositionX(Math.max(0, Math.min(100, drag.positionX - ((event.clientX - drag.x) / bounds.width) * 100)))
        setPositionY(Math.max(0, Math.min(100, drag.positionY - ((event.clientY - drag.y) / bounds.height) * 100)))
      }} onPointerUp={() => { dragRef.current = null }} onPointerCancel={() => { dragRef.current = null }} /></div>
      <div className="crop-controls">
        <label>Horizontal position<input type="range" min="0" max="100" value={positionX} onChange={(event) => setPositionX(Number(event.target.value))} /></label>
        <label>Vertical position<input type="range" min="0" max="100" value={positionY} onChange={(event) => setPositionY(Number(event.target.value))} /></label>
        <label>Zoom<input type="range" min="1" max="3" step="0.01" value={zoom} onChange={(event) => setZoom(Number(event.target.value))} /></label>
      </div>
      <p className="muted">The crop starts centered at the display's 5:3 ratio. Drag the preview or use the controls to adjust it; the image is never stretched.</p>
      <footer><button onClick={onCancel}>Cancel all</button><button className="primary-button" disabled={!image || processing} onClick={confirm}>{processing ? 'PROCESSING…' : queueLength > 1 ? 'Crop & next' : 'Crop & add page'}</button></footer>
    </section>
  </div>
}

function drawCroppedImage(canvas: HTMLCanvasElement, image: HTMLImageElement, positionX: number, positionY: number, zoom: number) {
  const targetRatio = canvas.width / canvas.height
  let cropWidth = image.naturalWidth
  let cropHeight = cropWidth / targetRatio
  if (cropHeight > image.naturalHeight) {
    cropHeight = image.naturalHeight
    cropWidth = cropHeight * targetRatio
  }
  cropWidth /= zoom
  cropHeight /= zoom
  const sourceX = (image.naturalWidth - cropWidth) * positionX
  const sourceY = (image.naturalHeight - cropHeight) * positionY
  const context = canvas.getContext('2d')
  if (!context) return
  context.clearRect(0, 0, canvas.width, canvas.height)
  context.drawImage(image, sourceX, sourceY, cropWidth, cropHeight, 0, 0, canvas.width, canvas.height)
}

function SettingsPage() {
  const [network, setNetwork] = useState<HotspotSettings | null>(null)
  const [system, setSystem] = useState<SystemInfo | null>(null)
  const [ssid, setSsid] = useState('InkPi-AP')
  const [password, setPassword] = useState('')
  const [security, setSecurity] = useState<HotspotSecurity>('wpa2')
  const [showPassword, setShowPassword] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    Promise.all([api.networkSettings(), api.systemSettings(), api.hotspotCredentials().catch(() => null)])
      .then(([settings, systemInfo, credentials]) => {
        setNetwork(settings)
        setSystem(systemInfo)
        setSsid(settings.ssid)
        setSecurity(settings.security)
        setPassword(credentials?.password ?? '')
      })
      .catch((reason: Error) => setMessage(reason.message))
  }, [])

  const save = async (enabled: boolean) => {
    setMessage('')
    if (enabled && security !== 'open' && password.length < 8) {
      setMessage('Enter the current or new hotspot password (at least 8 characters).')
      return
    }
    setSaving(true)
    try {
      const updated = await api.updateHotspot(
        { enabled, ssid: ssid.trim(), security, ...(enabled && security !== 'open' ? { password } : {}) },
      )
      setNetwork(updated)
      setSsid(updated.ssid)
      setShowPassword(false)
      setMessage(enabled ? 'Hotspot configuration applied.' : 'Hotspot disabled.')
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : 'Network request failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Page title="Settings" eyebrow="DEVICE CONFIGURATION">
      <div className="settings-grid">
        <Panel title="Device">
          <DefinitionList rows={[["Name", system?.device_name ?? '—'], ["Timezone", Intl.DateTimeFormat().resolvedOptions().timeZone], ["Firmware", system?.firmware_version ?? '—']]} />
        </Panel>
        <Panel title="Network" className="network-panel">
          <h3 className="settings-subheading">WiFi Hotspot</h3>
          <div className="network-status-row">
            <Status online={network?.enabled ?? false} />
            <span>{network?.enabled ? 'HOTSPOT ON' : 'HOTSPOT OFF'}</span>
          </div>
          <div className="settings-form">
            <label>SSID<input value={ssid} maxLength={32} onChange={(event) => setSsid(event.target.value)} /></label>
            <label>Security<select value={security} onChange={(event) => setSecurity(event.target.value as HotspotSecurity)}><option value="wpa2">WPA2</option><option value="wpa3">WPA3</option><option value="wpa2-wpa3">WPA2 / WPA3</option><option value="open">Open (no password)</option></select></label>
            <label className="password-setting">Password<div className="password-field"><input disabled={security === 'open'} type={showPassword ? 'text' : 'password'} value={password} minLength={8} maxLength={63} autoComplete="new-password" onChange={(event) => {
              setPassword(event.target.value)
            }} placeholder={security === 'open' ? 'Not required for an open network' : 'Stored in protected NetworkManager profile'} /><button disabled={security === 'open'} type="button" onClick={() => setShowPassword((value) => !value)} aria-pressed={showPassword} aria-label={showPassword ? 'Hide hotspot password' : 'Show hotspot password'}>{showPassword ? 'HIDE' : 'SHOW'}</button></div></label>
          </div>
          <DefinitionList rows={[["Connected devices", String(network?.connected_clients ?? '—')], ["Updated", network ? new Date(network.updated_at).toLocaleString() : '—']]} />
          <div className="settings-actions">
            <button className="primary-button" disabled={saving || !ssid.trim()} onClick={() => void save(true)}>{network?.enabled ? 'Apply & Restart' : 'Enable Hotspot'}</button>
            <button disabled={saving || !network?.enabled} onClick={() => void save(false)}>Disable</button>
          </div>
          {message && <p className="settings-message" role="status">{message}</p>}
          {network?.enabled && (security === 'open' || password) && <div className="wifi-qr"><QRCodeSVG value={wifiQrValue(ssid, password, security)} size={132} level="M" marginSize={2} title={`Connect to ${ssid}`} /><p>Scan to join {ssid}</p></div>}
          <p className="muted">The password is stored only in NetworkManager's protected hotspot profile and is available after login.</p>
        </Panel>
        <Panel title="Display Information">
          <DefinitionList rows={[["Resolution", "800 × 480"], ["Last refresh", system?.last_refresh ? new Date(system.last_refresh).toLocaleString() : 'Not reported'], ["Current revision", String(system?.display_revision ?? '—')], ["Device uptime", formatUptime(system?.uptime_seconds)]]} />
          <p className="muted">Refresh interval, partial count, and full-refresh policy remain private to the display service.</p>
        </Panel>
      </div>
    </Page>
  )
}

function wifiQrValue(ssid: string, password: string, security: HotspotSecurity): string {
  const escape = (value: string) => value.replace(/([\\;,:"])/g, '\\$1')
  return security === 'open' ? `WIFI:T:nopass;S:${escape(ssid)};;` : `WIFI:T:WPA;S:${escape(ssid)};P:${escape(password)};;`
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
