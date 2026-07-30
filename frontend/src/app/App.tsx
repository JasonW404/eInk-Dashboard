import { useEffect, useMemo, useRef, useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import Cropper from 'cropperjs'
import 'cropperjs/dist/cropper.css'
import { api, apiPath, type DisplayPage, type DisplayRevision, type HotspotSecurity, type HotspotSettings, type IntegrationSettings, type LatestReport, type SystemInfo, type Todo, type TodoDisplaySettings, type TodoSort } from '../api/client'
import { appPath, routeFromPathname, type AppRoute } from './basePath'

declare const __APP_VERSION__: string

type Route = AppRoute
type ThemeMode = 'auto' | 'light' | 'dark'

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
  const [theme, setTheme] = useState<ThemeMode>(() => {
    const saved = window.localStorage.getItem('inkpi-theme')
    return saved === 'light' || saved === 'dark' ? saved : 'auto'
  })

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const applyTheme = () => {
      const resolved = theme === 'auto' ? (media.matches ? 'dark' : 'light') : theme
      document.documentElement.dataset.theme = resolved
      document.documentElement.style.colorScheme = resolved
    }
    applyTheme()
    media.addEventListener('change', applyTheme)
    window.localStorage.setItem('inkpi-theme', theme)
    return () => media.removeEventListener('change', applyTheme)
  }, [theme])

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
  if (!authenticated) return <LoginPage onLogin={() => setAuthenticated(true)} theme={theme} setTheme={setTheme} />

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Brand />
        <Navigation route={route} navigate={navigate} />
        <div className="sidebar-footer">
          <ThemeSwitch value={theme} onChange={setTheme} />
          <button className="logout-button" onClick={() => void api.logout().then(() => setAuthenticated(false))}>LOG OUT</button>
          <p className="sidebar-foot">InkPi v{__APP_VERSION__}</p>
        </div>
      </aside>
      <main className="main-content">
        <header className="mobile-header"><Brand /><ThemeSwitch value={theme} onChange={setTheme} /></header>
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

function ThemeSwitch({ value, onChange }: { value: ThemeMode; onChange: (mode: ThemeMode) => void }) {
  const modes: ThemeMode[] = ['auto', 'light', 'dark']
  return (
    <div className="theme-toggle" role="group" aria-label="Color theme">
      {modes.map((mode) => (
        <button
          key={mode}
          className={value === mode ? 'active' : ''}
          onClick={() => onChange(mode)}
          aria-pressed={value === mode}
        >
          {mode.charAt(0).toUpperCase() + mode.slice(1)}
        </button>
      ))}
    </div>
  )
}

function LoginPage({ onLogin, theme, setTheme }: { onLogin: () => void; theme: ThemeMode; setTheme: (mode: ThemeMode) => void }) {
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
        <div className="login-card-top"><Brand /><ThemeSwitch value={theme} onChange={setTheme} /></div>
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
  const [previewOpen, setPreviewOpen] = useState(false)

  useEffect(() => {
    let active = true
    Promise.allSettled([api.health(), api.todos(), api.revision(), api.latestReports()])
      .then(([healthResult, todoResult, revisionResult, reportResult]) => {
        if (!active) return
        setOnline(healthResult.status === 'fulfilled')
        if (todoResult.status === 'fulfilled') setTodos(todoResult.value)
        if (revisionResult.status === 'fulfilled') setRevision(revisionResult.value)
        if (reportResult.status === 'fulfilled') setReports(reportResult.value)
      })
    return () => { active = false }
  }, [])

  const visibleTodos = todos
    .filter((todo) => todo.display_on_eink && !todo.completed)
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  const codex = reports.find((report) => report.type === 'codex')?.payload
  const github = reports.find((report) => report.type === 'github')?.payload
  const weeklyUsed = codexWeeklyUsed(codex)
  const githubCommits = reportNumber(github, 'commits', 'user_monthly_commit_count')
  const githubPrs = reportNumber(github, 'prs', 'pull_requests')

  return (
    <Page title="Overview" eyebrow="DEVICE AT A GLANCE">
      <section className="overview-grid">
        <div className="overview-left">
          <Panel title="Codex Usage" className="overview-codex">
            <p className="metric-label">WEEKLY USAGE</p>
            <p className="metric-value">{weeklyUsed === null ? '—' : `${weeklyUsed}%`}</p>
            <div className="progress"><span style={{ width: `${weeklyUsed ?? 0}%` }} /></div>
            <p className="muted">{codex ? `Plan ${String(codex.plan ?? '—')}` : 'Waiting for host agent report'}</p>
          </Panel>
          <Panel title="GitHub Activity" className="overview-github">
            <div className="github-content">
              <div className="split-metrics">
                <strong>{githubCommits ?? '—'}<small>COMMITS</small></strong>
                <strong>{githubPrs ?? '—'}<small>PRS</small></strong>
              </div>
              <span className="github-divider" aria-hidden="true" />
              <WebContributionCalendar payload={github} />
            </div>
          </Panel>
          <Panel title="Device Status" className="overview-device">
            <Status online={online} />
            <DefinitionList rows={[
              ['Device', 'InkPi'],
              ['API', online ? 'Connected' : 'Unavailable'],
              ['Version', `v${__APP_VERSION__}`],
            ]} />
          </Panel>
          <Panel title="eInk Preview" className="preview-panel overview-preview">
            <div className="preview-frame">
              {revision ? (
                <img
                  className="preview-zoomable"
                  src={`${apiPath('/api/display/image')}?revision=${revision.revision}`}
                  alt="Current 800 by 480 eInk output"
                  onClick={() => setPreviewOpen(true)}
                />
              ) : (
                <span>DISPLAY PREVIEW UNAVAILABLE</span>
              )}
            </div>
            {previewOpen && revision && (
              <div className="preview-lightbox" onClick={() => setPreviewOpen(false)}>
                <img src={`${apiPath('/api/display/image')}?revision=${revision.revision}`} alt="Enlarged eInk output" />
              </div>
            )}
            <div className="preview-meta">
              <span>REVISION #{revision?.revision ?? '—'}</span>
              <span>UPDATED {revision ? new Date(revision.updated_at).toLocaleString() : '—'}</span>
            </div>
          </Panel>
        </div>
        <Panel title="Todo Summary" className="overview-right overview-todo">
          <p className="metric-label">ON EINK · ACTIVE</p>
          {visibleTodos.length === 0
            ? <p className="muted">No active visible todos</p>
            : <ul className="summary-list">{visibleTodos.map((todo) => (
              <li key={todo.id}>□ {todo.title}</li>
            ))}</ul>}
        </Panel>
      </section>
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
  return <div className="web-calendar-wrap" aria-label="Current month GitHub contributions">
    <div className="web-calendar-weekdays">{['S','M','T','W','T','F','S'].map((d, i) => <span key={`${d}-${i}`}>{d}</span>)}</div>
    <div className="web-calendar">{cells.map((cell, index) => cell
    ? <i key={cell.key} className={cell.count === 0 ? '' : cell.count < 4 ? 'low' : 'high'} title={`${cell.key}: ${cell.count} contributions`} />
    : <i key={`blank-${index}`} className="blank" />)}</div>
  </div>
}

function TodoPage() {
  const [todos, setTodos] = useState<Todo[]>([])
  const [title, setTitle] = useState('')
  const [error, setError] = useState('')
  const [filter, setFilter] = useState<'all' | 'active' | 'completed'>(() => {
    const saved = window.localStorage.getItem('inkpi-todo-filter')
    return saved === 'active' || saved === 'completed' ? saved : 'all'
  })
  const [sort, setSort] = useState<TodoSort>(() => {
    const saved = window.localStorage.getItem('inkpi-todo-sort')
    return (saved as TodoSort) || 'manual'
  })
  const [displaySettings, setDisplaySettings] = useState<TodoDisplaySettings>({ show_completed: true, sort: 'manual' })
  const [editor, setEditor] = useState<{ mode: 'edit' | 'child'; todo: Todo } | null>(null)

  const load = () => Promise.all([api.todos(), api.todoDisplaySettings()]).then(([items, settings]) => { setTodos(items); setDisplaySettings(settings) }).catch((reason: Error) => setError(reason.message))
  useEffect(() => { void load() }, [])
  useEffect(() => { window.localStorage.setItem('inkpi-todo-filter', filter) }, [filter])
  useEffect(() => { window.localStorage.setItem('inkpi-todo-sort', sort) }, [sort])

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

  const move = (todo: Todo, offset: number) => {
    const siblings = todos.filter((item) => item.parent_id === todo.parent_id)
    const siblingIndex = siblings.findIndex((item) => item.id === todo.id)
    const targetSibling = siblings[siblingIndex + offset]
    if (!targetSibling) return
    const reordered = [...todos]
    const index = reordered.findIndex((item) => item.id === todo.id)
    const target = reordered.findIndex((item) => item.id === targetSibling.id)
    ;[reordered[index], reordered[target]] = [reordered[target], reordered[index]]
    void mutate(() => api.reorderTodos(reordered.map((todo) => todo.id)))
  }

  const filteredTodos = todos.filter((todo) => filter === 'all' || (filter === 'completed' ? todo.completed : !todo.completed))
  const visibleTodos = todoTreeRows(filteredTodos, sort)
  const saveDisplaySettings = (next: TodoDisplaySettings) => {
    setDisplaySettings(next)
    void mutate(() => api.updateTodoDisplaySettings(next))
  }

  return (
    <Page title="Todo List" eyebrow="PERSONAL QUEUE">
      <div className="todo-composer">
        <input value={title} onChange={(event) => setTitle(event.target.value)} onKeyDown={(event) => {
          if (event.key === 'Enter') void addTodo()
        }} placeholder="What needs to happen?" aria-label="New todo title" />
        <button className="primary-button" onClick={() => void addTodo()}>+ New Todo</button>
      </div>
      <section className="todo-view-toolbar" aria-label="Todo view controls">
        <div className="todo-filter"><span>FILTER</span><div>{(['all', 'active', 'completed'] as const).map((value) => <button className={filter === value ? 'active' : ''} key={value} onClick={() => setFilter(value)}>{value === 'all' ? `All ${todos.length}` : value === 'active' ? `Active ${todos.filter((todo) => !todo.completed).length}` : `Done ${todos.filter((todo) => todo.completed).length}`}</button>)}</div></div>
        <label className="todo-sort">SORT<select value={sort} onChange={(event) => setSort(event.target.value as TodoSort)}><TodoSortOptions includeManual /></select></label>
        <div className="eink-todo-settings"><span>ON EINK</span><label><input type="checkbox" checked={displaySettings.show_completed} onChange={(event) => saveDisplaySettings({ ...displaySettings, show_completed: event.target.checked })} /> Show completed</label><select aria-label="eInk todo order" value={displaySettings.sort} onChange={(event) => saveDisplaySettings({ ...displaySettings, sort: event.target.value as TodoSort })}><TodoSortOptions includeManual /></select></div>
      </section>
      {error && <p className="error-message">{error}</p>}
      <section className="todo-list">
        {visibleTodos.length === 0 && <div className="empty-state">{todos.length === 0 ? 'NO TODOS YET' : 'NO TODOS MATCH THIS FILTER'}</div>}
        {visibleTodos.map(({ todo, depth }) => {
          const siblings = todos.filter((item) => item.parent_id === todo.parent_id)
          const siblingIndex = siblings.findIndex((item) => item.id === todo.id)
          return <article className={`todo-item todo-depth-${depth}`} style={{ '--todo-depth': depth } as React.CSSProperties} key={todo.id}>
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
              {sort === 'manual' && filter === 'all' && <><button aria-label={`Move ${todo.title} up`} disabled={siblingIndex === 0} onClick={() => move(todo, -1)}>↑</button><button aria-label={`Move ${todo.title} down`} disabled={siblingIndex === siblings.length - 1} onClick={() => move(todo, 1)}>↓</button></>}
              {depth < 2 && <button onClick={() => setEditor({ mode: 'child', todo })}>+ CHILD</button>}
              <button onClick={() => setEditor({ mode: 'edit', todo })}>EDIT</button>
              <button onClick={() => void mutate(() => api.deleteTodo(todo.id))}>DELETE</button>
            </div>
          </article>
        })}
      </section>
      {editor && <TodoEditor
        mode={editor.mode}
        todo={editor.todo}
        onCancel={() => setEditor(null)}
        onConfirm={async (nextTitle) => {
          await mutate(() => editor.mode === 'edit'
            ? api.updateTodo(editor.todo.id, { title: nextTitle })
            : api.createTodo(nextTitle, editor.todo.id))
          setEditor(null)
        }}
      />}
    </Page>
  )
}

function TodoEditor({ mode, todo, onCancel, onConfirm }: { mode: 'edit' | 'child'; todo: Todo; onCancel: () => void; onConfirm: (title: string) => Promise<void> }) {
  const [title, setTitle] = useState(mode === 'edit' ? todo.title : '')
  const inputRef = useRef<HTMLInputElement>(null)
  useEffect(() => { inputRef.current?.focus() }, [])
  const submit = () => {
    const next = title.trim()
    if (next && (mode === 'child' || next !== todo.title)) void onConfirm(next)
  }
  return <div className="crop-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onCancel() }}>
    <section className="todo-editor-dialog" role="dialog" aria-modal="true" aria-labelledby="todo-editor-title">
      <header><div><p className="eyebrow">{mode === 'edit' ? 'UPDATE ITEM' : 'NEW CHILD ITEM'}</p><h2 id="todo-editor-title">{mode === 'edit' ? 'Edit todo' : `Add under “${todo.title}”`}</h2></div><button aria-label="Close" onClick={onCancel}>×</button></header>
      <form onSubmit={(event) => { event.preventDefault(); submit() }}>
        <label>TODO TITLE<input ref={inputRef} value={title} maxLength={500} onChange={(event) => setTitle(event.target.value)} /></label>
        <footer><button type="button" onClick={onCancel}>CANCEL</button><button type="submit" className="primary-button" disabled={!title.trim()}>{mode === 'edit' ? 'SAVE CHANGES' : 'ADD CHILD'}</button></footer>
      </form>
    </section>
  </div>
}

function TodoSortOptions({ includeManual }: { includeManual?: boolean }) {
  return <>{includeManual && <option value="manual">Custom order</option>}<option value="created_desc">Newest first</option><option value="created_asc">Oldest first</option><option value="completed_asc">Active first</option><option value="completed_desc">Completed first</option></>
}

function sortTodos(todos: Todo[], sort: TodoSort): Todo[] {
  return [...todos].sort((left, right) => {
    if (sort === 'created_asc' || sort === 'created_desc') {
      const result = new Date(left.created_at).getTime() - new Date(right.created_at).getTime()
      return (sort === 'created_desc' ? -result : result) || left.sort_order - right.sort_order
    }
    if (sort === 'completed_asc' || sort === 'completed_desc') {
      const result = Number(left.completed) - Number(right.completed)
      return (sort === 'completed_desc' ? -result : result) || left.sort_order - right.sort_order
    }
    return left.sort_order - right.sort_order
  })
}

function todoTreeRows(todos: Todo[], sort: TodoSort): Array<{ todo: Todo; depth: number }> {
  const included = new Set(todos.map((todo) => todo.id))
  const children = new Map<number | null, Todo[]>()
  todos.forEach((todo) => {
    const parent = todo.parent_id !== null && included.has(todo.parent_id) ? todo.parent_id : null
    children.set(parent, [...(children.get(parent) ?? []), todo])
  })
  const rows: Array<{ todo: Todo; depth: number }> = []
  const visit = (parent: number | null, depth: number) => {
    sortTodos(children.get(parent) ?? [], sort).forEach((todo) => {
      rows.push({ todo, depth })
      visit(todo.id, Math.min(depth + 1, 2))
    })
  }
  visit(null, 0)
  return rows
}

function PagesPage() {
  const [pages, setPages] = useState<DisplayPage[]>([])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [cropQueue, setCropQueue] = useState<File[]>([])
  const [textEditorOpen, setTextEditorOpen] = useState(false)
  const [editingPage, setEditingPage] = useState<DisplayPage | null>(null)
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
      <div className="page-toolbar-actions">
        <button className="text-page-button" disabled={busy} onClick={() => setTextEditorOpen(true)}>+ New text page</button>
        <label className="upload-button">+ Upload photos<input disabled={busy} type="file" accept="image/*" multiple onChange={(event) => {
          const files = Array.from(event.target.files ?? [])
          if (files.length) setCropQueue(files)
          event.target.value = ''
        }} /></label>
      </div>
    </section>
    {message && <p className="settings-message" role="status">{message}</p>}
    <div className="pages-list">
      {pages.length === 0 && <div className="empty-state">UPLOAD PHOTOS TO EXTEND THE DISPLAY LOOP</div>}
      {pages.map((page, index) => <article className="page-row" key={page.id}>
        <div className="page-thumbnail">{page.kind === 'dashboard'
          ? <img src={`${apiPath('/api/display/dashboard-image')}?v=${encodeURIComponent(page.updated_at)}`} alt="Dashboard preview" />
          : <img src={api.pageImage(page.id, page.updated_at)} alt={`Preview of ${page.name}`} />}</div>
        <div className="page-card-body">
          <div className="page-copy"><strong>{page.name}</strong><span>{page.kind === 'dashboard' ? 'LIVE INKPI OVERVIEW' : page.kind === 'text' ? `TEXT PAGE · POSITION ${index + 1}` : `PHOTO PAGE · POSITION ${index + 1}`}</span></div>
          <label>Interval<select value={page.interval_seconds} disabled={busy} onChange={(event) => void mutate(() => api.updatePage(page.id, { interval_seconds: Number(event.target.value) }))}><option value={30}>30 sec</option><option value={60}>1 min</option><option value={300}>5 min</option><option value={900}>15 min</option><option value={3600}>1 hour</option></select></label>
          <div className="page-card-actions"><div className="page-order"><button disabled={busy || index === 0} onClick={() => move(index, -1)}>↑</button><button disabled={busy || index === pages.length - 1} onClick={() => move(index, 1)}>↓</button></div>{page.kind === 'text' && <button className="edit-page" disabled={busy} onClick={() => setEditingPage(page)}>EDIT</button>}<label className="page-enabled"><input type="checkbox" checked={page.enabled} disabled={busy} onChange={() => void mutate(() => api.updatePage(page.id, { enabled: !page.enabled }))} /> ACTIVE</label><button className="delete-page" disabled={busy || page.kind === 'dashboard'} onClick={() => void mutate(() => api.deletePage(page.id))}>{page.kind === 'dashboard' ? 'BUILT IN' : 'DELETE'}</button></div>
        </div>
      </article>)}
    </div>
    <p className="muted">Active pages cycle in this order. Photos are cropped to the 800 × 480 display ratio without stretching; each page's interval controls when the physical display advances.</p>
    {cropQueue[0] && <ImageCropDialog file={cropQueue[0]} queueLength={cropQueue.length} onCancel={() => setCropQueue([])} onConfirm={async (cropped) => {
      const uploaded = await mutate(() => api.uploadPage(cropped))
      if (uploaded) setCropQueue((queue) => queue.slice(1))
      return uploaded
    }} />}
    {textEditorOpen && <TextPageEditor onCancel={() => setTextEditorOpen(false)} onConfirm={async (pageName, content) => {
      const created = await mutate(() => api.createTextPage(pageName, content))
      if (created) setTextEditorOpen(false)
      return created
    }} />}
    {editingPage && <TextPageEditor initialPage={editingPage} onCancel={() => setEditingPage(null)} onConfirm={async (pageName, content) => {
      const updated = await mutate(() => api.updatePage(editingPage.id, { name: pageName, content }))
      if (updated) setEditingPage(null)
      return updated
    }} />}
  </Page>
}

function ImageCropDialog({ file, queueLength, onCancel, onConfirm }: { file: File; queueLength: number; onCancel: () => void; onConfirm: (file: File) => Promise<boolean> }) {
  const imageRef = useRef<HTMLImageElement>(null)
  const previewRef = useRef<HTMLCanvasElement>(null)
  const cropperRef = useRef<Cropper | null>(null)
  const frameRef = useRef<number | null>(null)
  const [sourceUrl, setSourceUrl] = useState('')
  const [tone, setTone] = useState(0)
  const [detail, setDetail] = useState(50)
  const [ready, setReady] = useState(false)
  const [processing, setProcessing] = useState(false)

  useEffect(() => {
    const url = URL.createObjectURL(file)
    setSourceUrl(url); setTone(0); setDetail(50); setReady(false)
    return () => URL.revokeObjectURL(url)
  }, [file])

  useEffect(() => {
    const image = imageRef.current
    if (!image || !sourceUrl) return
    const render = () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current)
      frameRef.current = requestAnimationFrame(() => renderFourGrayPreview(cropperRef.current, previewRef.current, tone, detail))
    }
    const cropper = new Cropper(image, {
      aspectRatio: 5 / 3, viewMode: 1, dragMode: 'move', autoCropArea: 0.86,
      responsive: true, restore: false, guides: true, center: true,
      movable: true, zoomable: true, zoomOnTouch: true, zoomOnWheel: true,
      wheelZoomRatio: 0.08, cropBoxMovable: true, cropBoxResizable: true,
      toggleDragModeOnDblclick: false,
      ready() { setReady(true); render() }, crop: render, zoom: render,
    })
    cropperRef.current = cropper
    return () => { if (frameRef.current !== null) cancelAnimationFrame(frameRef.current); cropper.destroy(); cropperRef.current = null }
  }, [sourceUrl])

  useEffect(() => { renderFourGrayPreview(cropperRef.current, previewRef.current, tone, detail) }, [tone, detail])

  const confirm = () => {
    const canvas = previewRef.current
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
      <div className="crop-workspace"><div className="crop-stage"><img ref={imageRef} src={sourceUrl} alt="Source to crop" /></div><div className="gray-preview"><span>FINAL 4-GRAY PREVIEW</span><canvas ref={previewRef} width={800} height={480} /></div></div>
      <div className="photo-controls">
        <label><span>Lightness <b>{tone > 0 ? `+${tone}` : tone}</b></span><input type="range" min="-100" max="100" value={tone} onChange={(event) => setTone(Number(event.target.value))} /></label>
        <label><span>Detail <b>{detail}</b></span><input type="range" min="0" max="100" value={detail} onChange={(event) => setDetail(Number(event.target.value))} /></label>
      </div>
      <p className="muted">Drag or resize the 5:3 crop box. Move the image, pinch on touch screens, or use the mouse wheel to zoom. Lightness applies highlight-safe gamma correction; Detail combines contrast and restrained ordered dithering.</p>
      <footer><button onClick={onCancel}>Cancel all</button><button className="primary-button" disabled={!ready || processing} onClick={confirm}>{processing ? 'PROCESSING…' : queueLength > 1 ? 'Crop & next' : 'Crop & add page'}</button></footer>
    </section>
  </div>
}

function renderFourGrayPreview(cropper: Cropper | null, output: HTMLCanvasElement | null, tone: number, detail: number) {
  if (!cropper || !output) return
  const cropped = cropper.getCroppedCanvas({ width: 800, height: 480, imageSmoothingEnabled: true, imageSmoothingQuality: 'high' })
  const context = output.getContext('2d', { willReadFrequently: true })
  if (!context) return
  context.drawImage(cropped, 0, 0, 800, 480)
  const frame = context.getImageData(0, 0, 800, 480)
  const gamma = 2 ** (-tone / 100)
  const contrast = 0.72 + detail * 0.012
  const dither = 8 + detail * 0.28
  const bayer = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5]
  for (let pixel = 0; pixel < frame.data.length; pixel += 4) {
    const index = pixel / 4
    const luminance = 0.2126 * frame.data[pixel] + 0.7152 * frame.data[pixel + 1] + 0.0722 * frame.data[pixel + 2]
    const corrected = 255 * ((Math.max(0, Math.min(255, (255 * ((luminance / 255) ** gamma) - 128) * contrast + 128))) / 255)
    const x = index % 800; const y = Math.floor(index / 800)
    const offset = ((bayer[(y % 4) * 4 + (x % 4)] - 7.5) / 16) * dither
    const gray = Math.max(0, Math.min(255, Math.round((corrected + offset) / 85) * 85))
    frame.data[pixel] = gray; frame.data[pixel + 1] = gray; frame.data[pixel + 2] = gray; frame.data[pixel + 3] = 255
  }
  context.putImageData(frame, 0, 0)
}

function TextPageEditor({ initialPage, onCancel, onConfirm }: { initialPage?: DisplayPage; onCancel: () => void; onConfirm: (name: string, content: string) => Promise<boolean> }) {
  const parsed = useMemo(() => {
    if (!initialPage?.content) return null
    try { return JSON.parse(initialPage.content) as Record<string, unknown> } catch { return null }
  }, [initialPage])
  const [name, setName] = useState(initialPage?.name ?? 'Text Page')
  const [text, setText] = useState(typeof parsed?.text === 'string' ? parsed.text : '')
  const [textAlign, setTextAlign] = useState<'left' | 'center' | 'right'>((parsed?.textAlign as 'left' | 'center' | 'right') ?? 'center')
  const [horizontalAlign, setHorizontalAlign] = useState<'left' | 'center' | 'right'>((parsed?.horizontalAlign as 'left' | 'center' | 'right') ?? 'center')
  const [verticalAlign, setVerticalAlign] = useState<'top' | 'center' | 'bottom'>((parsed?.verticalAlign as 'top' | 'center' | 'bottom') ?? 'center')
  const [paddingTop, setPaddingTop] = useState(typeof parsed?.paddingTop === 'number' ? parsed.paddingTop : 20)
  const [paddingBottom, setPaddingBottom] = useState(typeof parsed?.paddingBottom === 'number' ? parsed.paddingBottom : 20)
  const [paddingLeft, setPaddingLeft] = useState(typeof parsed?.paddingLeft === 'number' ? parsed.paddingLeft : 20)
  const [paddingRight, setPaddingRight] = useState(typeof parsed?.paddingRight === 'number' ? parsed.paddingRight : 20)
  const [saving, setSaving] = useState(false)
  const isEditing = !!initialPage

  const scalerRef = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(1)

  useEffect(() => {
    const el = scalerRef.current
    if (!el) return
    const update = () => {
      const w = el.clientWidth
      setScale(w / 800)
    }
    update()
    const observer = new ResizeObserver(update)
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const previewUrl = useMemo(() => {
    const params = new URLSearchParams({
      text,
      textAlign, horizontalAlign, verticalAlign,
      paddingTop: String(paddingTop), paddingBottom: String(paddingBottom),
      paddingLeft: String(paddingLeft), paddingRight: String(paddingRight),
    })
    return apiPath(`/text.html?${params}`)
  }, [text, textAlign, horizontalAlign, verticalAlign, paddingTop, paddingBottom, paddingLeft, paddingRight])

  const contentJson = JSON.stringify({ text, textAlign, horizontalAlign, verticalAlign, paddingTop, paddingBottom, paddingLeft, paddingRight })

  const confirm = async () => {
    if (!text.trim()) return
    setSaving(true)
    await onConfirm(name || 'Text Page', contentJson)
    setSaving(false)
  }

  return <div className="crop-backdrop" role="presentation">
    <section className="text-editor-dialog" role="dialog" aria-modal="true" aria-labelledby="text-editor-title">
      <header>
        <div><span className="eyebrow">{isEditing ? 'EDIT TEXT PAGE' : 'NEW TEXT PAGE'}</span><h2 id="text-editor-title">{isEditing ? 'Edit Text Page' : 'Create Text Page'}</h2></div>
        <button onClick={onCancel} aria-label="Cancel">×</button>
      </header>
      <div className="text-editor-workspace">
        <div className="text-editor-preview">
          <span>PREVIEW · 800 × 480</span>
          <div className="text-preview-scaler" ref={scalerRef}>
            <iframe src={previewUrl} title="Text page preview" className="text-preview-frame" style={{ transform: `scale(${scale})` }} />
          </div>
        </div>
        <div className="text-editor-controls">
          <div className="text-style-controls">
            <label><span>NAME</span><input type="text" value={name} onChange={(e) => setName(e.target.value)} /></label>
            <div className="style-row">
              <span>TEXT ALIGN</span>
              <div className="button-group">
                <button className={textAlign === 'left' ? 'active' : ''} onClick={() => setTextAlign('left')}>L</button>
                <button className={textAlign === 'center' ? 'active' : ''} onClick={() => setTextAlign('center')}>C</button>
                <button className={textAlign === 'right' ? 'active' : ''} onClick={() => setTextAlign('right')}>R</button>
              </div>
            </div>
            <div className="style-row">
              <span>HORIZONTAL</span>
              <div className="button-group">
                <button className={horizontalAlign === 'left' ? 'active' : ''} onClick={() => setHorizontalAlign('left')}>L</button>
                <button className={horizontalAlign === 'center' ? 'active' : ''} onClick={() => setHorizontalAlign('center')}>C</button>
                <button className={horizontalAlign === 'right' ? 'active' : ''} onClick={() => setHorizontalAlign('right')}>R</button>
              </div>
            </div>
            <div className="style-row">
              <span>VERTICAL</span>
              <div className="button-group">
                <button className={verticalAlign === 'top' ? 'active' : ''} onClick={() => setVerticalAlign('top')}>T</button>
                <button className={verticalAlign === 'center' ? 'active' : ''} onClick={() => setVerticalAlign('center')}>C</button>
                <button className={verticalAlign === 'bottom' ? 'active' : ''} onClick={() => setVerticalAlign('bottom')}>B</button>
              </div>
            </div>
            <div className="style-row padding-row">
              <span>PADDING</span>
              <label>T<input type="number" min={0} max={200} value={paddingTop} onChange={(e) => setPaddingTop(Number(e.target.value))} /></label>
              <label>B<input type="number" min={0} max={200} value={paddingBottom} onChange={(e) => setPaddingBottom(Number(e.target.value))} /></label>
              <label>L<input type="number" min={0} max={200} value={paddingLeft} onChange={(e) => setPaddingLeft(Number(e.target.value))} /></label>
              <label>R<input type="number" min={0} max={200} value={paddingRight} onChange={(e) => setPaddingRight(Number(e.target.value))} /></label>
            </div>
          </div>
          <label className="text-input-label"><span>MARKDOWN CONTENT</span><textarea className="text-input-area" value={text} onChange={(e) => setText(e.target.value)} placeholder="Enter Markdown here... (# heading, **bold**, *italic*, - list)" /></label>
        </div>
      </div>
      <footer>
        <button onClick={onCancel}>Cancel</button>
        <button className="primary-button" disabled={!text.trim() || saving} onClick={confirm}>{saving ? 'SAVING…' : isEditing ? 'Save changes' : 'Create page'}</button>
      </footer>
    </section>
  </div>
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
  const [integrations, setIntegrations] = useState<IntegrationSettings | null>(null)
  const [githubEnabled, setGithubEnabled] = useState(false)
  const [githubUsername, setGithubUsername] = useState('')
  const [githubOrganization, setGithubOrganization] = useState('')
  const [githubCommitEmail, setGithubCommitEmail] = useState('')
  const [githubExtraRepos, setGithubExtraRepos] = useState('')
  const [githubToken, setGithubToken] = useState('')
  const [clearGithubToken, setClearGithubToken] = useState(false)
  const [integrationMessage, setIntegrationMessage] = useState('')
  const [savingIntegration, setSavingIntegration] = useState(false)

  useEffect(() => {
    Promise.all([api.networkSettings(), api.systemSettings(), api.hotspotCredentials().catch(() => null), api.integrationSettings()])
      .then(([settings, systemInfo, credentials, integrationSettings]) => {
        setNetwork(settings)
        setSystem(systemInfo)
        setSsid(settings.ssid)
        setSecurity(settings.security)
        setPassword(credentials?.password ?? '')
        setIntegrations(integrationSettings)
        setGithubEnabled(integrationSettings.github.enabled)
        setGithubUsername(integrationSettings.github.username)
        setGithubOrganization(integrationSettings.github.organization)
        setGithubCommitEmail(integrationSettings.github.commit_email)
        setGithubExtraRepos(integrationSettings.github.extra_repos.join('\n'))
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

  const saveGitHub = async () => {
    setSavingIntegration(true)
    setIntegrationMessage('')
    try {
      const updated = await api.updateGitHubIntegration({
        enabled: githubEnabled,
        username: githubUsername.trim(),
        organization: githubOrganization.trim(),
        commit_email: githubCommitEmail.trim(),
        extra_repos: githubExtraRepos.split(/\s+/).filter(Boolean),
        ...(githubToken ? { token: githubToken } : {}),
        clear_token: clearGithubToken,
      })
      setIntegrations(updated)
      setGithubToken('')
      setClearGithubToken(false)
      setIntegrationMessage('GitHub settings saved. Cloud collection has been scheduled.')
    } catch (reason) {
      setIntegrationMessage(reason instanceof Error ? reason.message : 'GitHub settings could not be saved')
    } finally {
      setSavingIntegration(false)
    }
  }

  return (
    <Page title="Settings" eyebrow="DEVICE CONFIGURATION">
      <section className="settings-grid">
        <div className="settings-left">
          <Panel title="Device">
            <DefinitionList rows={[
              ['Name', system?.device_name ?? '—'],
              ['Timezone', Intl.DateTimeFormat().resolvedOptions().timeZone],
              ['Firmware', system?.firmware_version ?? '—'],
            ]} />
          </Panel>
          <Panel title="Display Information">
            <DefinitionList rows={[
              ['Resolution', '800 × 480'],
              ['Last refresh', system?.last_refresh ? new Date(system.last_refresh).toLocaleString() : 'Not reported'],
              ['Current revision', String(system?.display_revision ?? '—')],
              ['Device uptime', formatUptime(system?.uptime_seconds)],
            ]} />
          </Panel>
        </div>
        <Panel title="Network" className="settings-right">
          <div className="network-status-row">
            <Status online={network?.enabled ?? false} />
            <span>{network?.enabled ? 'HOTSPOT ON' : 'HOTSPOT OFF'}</span>
          </div>
          <div className="network-body">
            <div className="network-form-col">
              <div className="settings-form">
                <label>SSID<input value={ssid} maxLength={32} onChange={(event) => setSsid(event.target.value)} /></label>
                <label>Security<select value={security} onChange={(event) => setSecurity(event.target.value as HotspotSecurity)}><option value="wpa2">WPA2</option><option value="wpa3">WPA3</option><option value="wpa2-wpa3">WPA2 / WPA3</option><option value="open">Open (no password)</option></select></label>
                <label className="password-setting">Password<div className="password-field"><input disabled={security === 'open'} type={showPassword ? 'text' : 'password'} value={password} minLength={8} maxLength={63} autoComplete="new-password" onChange={(event) => {
                  setPassword(event.target.value)
                }} placeholder={security === 'open' ? 'Not required for an open network' : 'Sent securely to the Pi network service'} /><button disabled={security === 'open'} type="button" onClick={() => setShowPassword((value) => !value)} aria-pressed={showPassword} aria-label={showPassword ? 'Hide hotspot password' : 'Show hotspot password'}>{showPassword ? 'HIDE' : 'SHOW'}</button></div></label>
              </div>
              <DefinitionList rows={[
                ['Connected devices', String(network?.connected_clients ?? '—')],
                ['Updated', network ? new Date(network.updated_at).toLocaleString() : '—'],
                ['Last operation', String(network?.operation?.status ?? 'idle')],
                ['Pi network seen', typeof network?.operation?.network_last_seen === 'string' ? new Date(network.operation.network_last_seen).toLocaleString() : 'Never'],
              ]} />
              <div className="settings-actions">
                <button className="primary-button" disabled={saving || !ssid.trim()} onClick={() => void save(true)}>{network?.enabled ? 'Apply & Restart' : 'Enable Hotspot'}</button>
                <button disabled={saving || !network?.enabled} onClick={() => void save(false)}>Disable</button>
              </div>
              {message && <p className="settings-message" role="status">{message}</p>}
              <p className="muted">Cloud queues this desired state. The authenticated Pi network service polls it, applies the NetworkManager change locally, and reports the result.</p>
            </div>
            {network?.enabled && (security === 'open' || password) && <div className="wifi-qr"><QRCodeSVG value={wifiQrValue(ssid, password, security)} size={132} level="M" marginSize={2} title={`Connect to ${ssid}`} /><p>Scan to join {ssid}</p></div>}
          </div>
        </Panel>
      </section>
      <section className="integration-grid">
        <Panel title="GitHub Activity">
          <div className="integration-status"><Status online={githubEnabled && Boolean(githubUsername)} /><span>{integrations?.github.token_configured ? 'AUTHENTICATED' : 'PUBLIC DATA ONLY'}</span></div>
          <div className="settings-form integration-form">
            <label className="toggle-setting"><input type="checkbox" checked={githubEnabled} onChange={(event) => setGithubEnabled(event.target.checked)} /> Enable Cloud collection</label>
            <label>Watching account<input value={githubUsername} maxLength={120} placeholder="GitHub username" onChange={(event) => setGithubUsername(event.target.value)} /></label>
            <label>Organization<input value={githubOrganization} maxLength={120} placeholder="Optional organization" onChange={(event) => setGithubOrganization(event.target.value)} /></label>
            <label>Commit email<input value={githubCommitEmail} maxLength={320} placeholder="Optional commit identity" onChange={(event) => setGithubCommitEmail(event.target.value)} /></label>
            <label className="wide-setting">Additional repositories<textarea value={githubExtraRepos} placeholder={'owner/repository\\none per line'} onChange={(event) => setGithubExtraRepos(event.target.value)} /></label>
            <label className="wide-setting">GitHub token<input type="password" value={githubToken} autoComplete="new-password" placeholder={integrations?.github.token_configured ? 'Token is configured; leave blank to keep it' : 'Optional for public data'} onChange={(event) => setGithubToken(event.target.value)} /></label>
            {integrations?.github.token_configured && <label className="toggle-setting wide-setting"><input type="checkbox" checked={clearGithubToken} onChange={(event) => setClearGithubToken(event.target.checked)} /> Remove stored token</label>}
          </div>
          <div className="settings-actions"><button className="primary-button" disabled={savingIntegration || (githubEnabled && !githubUsername.trim())} onClick={() => void saveGitHub()}>{savingIntegration ? 'SAVING…' : 'Save GitHub settings'}</button></div>
          {integrationMessage && <p className="settings-message" role="status">{integrationMessage}</p>}
          <p className="muted">The token is stored by InkPi Cloud and is never returned to the browser. A token is recommended to avoid anonymous rate limits and include authorized private activity.</p>
        </Panel>
        <Panel title="Codex Usage">
          <div className="integration-status"><Status online={false} /><span>HOST AGENT REQUIRED</span></div>
          <DefinitionList rows={[
            ['Source', 'Local Codex account session'],
            ['API token', 'Not supported for personal quota'],
            ['Current collector', integrations?.codex.source ?? 'host-agent'],
          ]} />
          <p className="muted">{integrations?.codex.detail ?? 'Checking Codex capability…'}</p>
          <p className="settings-note">OpenAI Admin API keys can report API-platform requests, tokens, and costs. Those values are separate from the ChatGPT/Codex weekly allowance and cannot replace its remaining-percentage metric.</p>
        </Panel>
      </section>
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
