import { useEffect, useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { api, type DisplayContext, type DisplayRevision, type LatestReport, type Todo, type TodoDisplaySettings, type TodoSort } from '../api/client'

interface EinkData {
  todos: Todo[]
  revision: DisplayRevision | null
  reports: LatestReport[]
  context: DisplayContext | null
  todoSettings: TodoDisplaySettings
  error: string | null
}

export function EinkDisplay() {
  const [data, setData] = useState<EinkData>({ todos: [], revision: null, reports: [], context: null, todoSettings: { show_completed: true, sort: 'manual' }, error: null })
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let active = true
    Promise.all([
      api.todos(),
      api.revision(),
      api.latestReports(),
      api.displayContext().catch(() => null),
      api.todoDisplaySettings(),
    ])
      .then(([todos, revision, reports, context, todoSettings]) => {
        if (active) setData({ todos, revision, reports, context, todoSettings, error: null })
      })
      .catch((reason: Error) => {
        if (active) setData({ todos: [], revision: null, reports: [], context: null, todoSettings: { show_completed: true, sort: 'manual' }, error: reason.message })
      })
      .finally(() => {
        if (active) setReady(true)
      })
    return () => { active = false }
  }, [])

  const visibleTodos = sortEinkTodos(data.todos.filter((todo) => todo.display_on_eink && (data.todoSettings.show_completed || !todo.completed)), data.todoSettings.sort).slice(0, 6)
  const codex = data.reports.find((report) => report.type === 'codex')?.payload
  const github = data.reports.find((report) => report.type === 'github')?.payload
  const weeklyUsed = codexWeeklyUsed(codex)
  const commits = reportNumber(github, 'commits', 'user_monthly_commit_count')
  const prs = reportNumber(github, 'prs', 'pull_requests')
  const reset = codexWeeklyReset(codex)
  const today = formatHeaderDate(new Date())

  return (
    <main className="eink-display" data-eink-ready={ready ? 'true' : 'false'}>
      <header className="eink-header">
        <div>
          <strong>INKPI</strong>
          <span>AMBIENT PRODUCTIVITY TERMINAL</span>
        </div>
        <time className="eink-header-date">{today}</time>
        <div className="eink-header-meta">
          <span>{data.error ? 'OFFLINE' : 'ONLINE'} | {data.revision?.revision.slice(0, 8).toUpperCase() ?? '—'}</span>
        </div>
      </header>

      <div className="eink-grid">
        <EinkBlock title="TODO" subtitle="VISIBLE ON DEVICE" className="eink-todos">
          {visibleTodos.length === 0 ? (
            <p className="eink-empty">NO ACTIVE ITEMS</p>
          ) : (
            <ol className="eink-todo-list">
              {visibleTodos.map((todo) => (
                <li key={todo.id} className={todo.completed ? 'complete' : ''}>
                  <span>{todo.completed ? '■' : '□'}</span>
                  <strong>{todo.title}</strong>
                </li>
              ))}
            </ol>
          )}
        </EinkBlock>

        <div className="eink-side">
          <EinkBlock title="CODEX" subtitle="WEEKLY USAGE">
            <div className="eink-meter"><span style={{ width: `${weeklyUsed ?? 0}%` }} /></div>
            <div className="eink-codex-copy">
              <p className="eink-placeholder">
                {weeklyUsed === null ? 'AWAITING HOST AGENT' : `${String(codex?.plan ?? 'PLUS').toUpperCase()} · ${weeklyUsed}% · RESET @ ${reset ?? '—'}`}
              </p>
            </div>
          </EinkBlock>
          <EinkBlock title="GITHUB" subtitle="ALL REPOSITORIES">
            <div className="eink-github-content">
              <div className="eink-pair"><b>{commits ?? '—'}<small>COMMITS</small></b><b>{prs ?? '—'}<small>PRS</small></b></div>
              <span className="eink-github-divider" aria-hidden="true" />
              <ContributionCalendar payload={github} />
            </div>
          </EinkBlock>
          <EinkBlock title="SYSTEM" subtitle="NETWORK ACCESS">
            <HotspotAccess context={data.context} />
          </EinkBlock>
        </div>
      </div>
    </main>
  )
}

function sortEinkTodos(todos: Todo[], sort: TodoSort): Todo[] {
  return [...todos].sort((left, right) => {
    if (sort.startsWith('created_')) {
      const result = new Date(left.created_at).getTime() - new Date(right.created_at).getTime()
      return (sort === 'created_desc' ? -result : result) || left.sort_order - right.sort_order
    }
    if (sort.startsWith('completed_')) {
      const result = Number(left.completed) - Number(right.completed)
      return (sort === 'completed_desc' ? -result : result) || left.sort_order - right.sort_order
    }
    return left.sort_order - right.sort_order
  })
}

function HotspotAccess({ context }: { context: DisplayContext | null }) {
  if (!context?.hotspot_enabled) {
    return <div className="eink-system-idle"><span>HOTSPOT · DISABLED</span></div>
  }
  return (
    <div className="eink-hotspot">
      <div>
        <span>HOTSPOT · ENABLED</span>
        <strong>{context.hotspot_ssid ?? 'INKPI'}</strong>
      </div>
      {context.wifi_qr_payload && (
        <QRCodeSVG value={context.wifi_qr_payload} size={68} level="M" marginSize={0} />
      )}
    </div>
  )
}

function ContributionCalendar({ payload }: { payload: Record<string, unknown> | undefined }) {
  const counts = contributionCounts(payload)
  const today = startOfLocalDay(new Date())
  const first = new Date(today.getFullYear(), today.getMonth(), 1)
  const last = new Date(today.getFullYear(), today.getMonth() + 1, 0)
  const cells: Array<{ day: Date | null; count: number; today: boolean }> = []
  for (let index = 0; index < first.getDay(); index += 1) cells.push({ day: null, count: 0, today: false })
  for (let date = 1; date <= last.getDate(); date += 1) {
    const day = new Date(today.getFullYear(), today.getMonth(), date)
    cells.push({ day, count: counts.get(localDateKey(day)) ?? 0, today: date === today.getDate() })
  }
  return (
    <div className="eink-calendar-wrap" aria-label="Current month GitHub contributions">
      <div className="eink-calendar-weekdays">{['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((day, index) => <span key={`${day}-${index}`}>{day}</span>)}</div>
      <div className="eink-calendar">
        {cells.map(({ day, count, today: isToday }, index) => (
          day ? <i className={`${count === 0 ? 'empty' : count <= 3 ? 'hatched' : 'solid'}${isToday ? ' today' : ''}`} title={`${count} contributions`} key={localDateKey(day)} /> : <i className="blank" key={`blank-${index}`} />
        ))}
      </div>
    </div>
  )
}

function contributionCounts(payload: Record<string, unknown> | undefined): Map<string, number> {
  const result = new Map<string, number>()
  const contributions = payload?.contributions
  if (!Array.isArray(contributions)) return result
  for (const item of contributions) {
    if (typeof item !== 'object' || item === null) continue
    const record = item as Record<string, unknown>
    const day = record.day
    const count = record.commit_count
    if (typeof day === 'string' && typeof count === 'number') result.set(day, count)
  }
  return result
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

function codexWeeklyReset(payload: Record<string, unknown> | undefined): string | null {
  const windows = payload?.windows
  if (!Array.isArray(windows)) return null
  const weekly = windows.find((window) => (
    typeof window === 'object' && window !== null && String((window as Record<string, unknown>).label).includes('WEEKLY')
  )) as Record<string, unknown> | undefined
  const raw = weekly?.resets_at
  if (typeof raw !== 'string') return null
  const reset = new Date(raw)
  if (Number.isNaN(reset.getTime())) return null
  const month = String(reset.getMonth() + 1).padStart(2, '0')
  const day = String(reset.getDate()).padStart(2, '0')
  const clock = reset.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false })
  return `${month}/${day} ${clock}`
}

function formatHeaderDate(value: Date): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year} / ${month} / ${day}`
}

function startOfLocalDay(value: Date): Date {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate())
}

function localDateKey(value: Date): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function EinkBlock({
  title,
  subtitle,
  className = '',
  children,
}: {
  title: string
  subtitle: string
  className?: string
  children: React.ReactNode
}) {
  return (
    <section className={`eink-block ${className}`}>
      <header><strong>{title}</strong><span>{subtitle}</span></header>
      <div className="eink-block-body">{children}</div>
    </section>
  )
}
