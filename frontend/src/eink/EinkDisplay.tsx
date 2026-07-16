import { useEffect, useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { api, type DisplayContext, type DisplayRevision, type LatestReport, type Todo } from '../api/client'

interface EinkData {
  todos: Todo[]
  revision: DisplayRevision | null
  reports: LatestReport[]
  context: DisplayContext | null
  error: string | null
}

export function EinkDisplay() {
  const [data, setData] = useState<EinkData>({ todos: [], revision: null, reports: [], context: null, error: null })
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let active = true
    Promise.all([
      api.todos(),
      api.revision(),
      api.latestReports(),
      api.displayContext().catch(() => null),
    ])
      .then(([todos, revision, reports, context]) => {
        if (active) setData({ todos, revision, reports, context, error: null })
      })
      .catch((reason: Error) => {
        if (active) setData({ todos: [], revision: null, reports: [], context: null, error: reason.message })
      })
      .finally(() => {
        if (active) setReady(true)
      })
    return () => { active = false }
  }, [])

  const visibleTodos = data.todos.filter((todo) => todo.display_on_eink).slice(0, 8)
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
          <span>REV #{data.revision?.revision ?? '—'}</span>
          <span>{data.error ? 'DATA OFFLINE' : 'SYSTEM ONLINE'}</span>
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
                {weeklyUsed === null ? 'AWAITING HOST AGENT' : `${weeklyUsed}% USED · ${String(codex?.plan ?? '—').toUpperCase()}`}
              </p>
              {reset && <p className="eink-reset">RESET {reset}</p>}
            </div>
          </EinkBlock>
          <EinkBlock title="GITHUB" subtitle="ALL REPOSITORIES">
            <div className="eink-pair"><b>{commits ?? '—'}<small>COMMITS</small></b><b>{prs ?? '—'}<small>PRS</small></b></div>
            <ContributionCalendar payload={github} />
          </EinkBlock>
          <EinkBlock title="SYSTEM" subtitle="NETWORK ACCESS">
            <HotspotAccess context={data.context} />
          </EinkBlock>
        </div>
      </div>
    </main>
  )
}

function HotspotAccess({ context }: { context: DisplayContext | null }) {
  if (!context?.hotspot_enabled) {
    return <p className="eink-system-idle">HOTSPOT OFF</p>
  }
  return (
    <div className="eink-hotspot">
      <div>
        <span>HOTSPOT SSID</span>
        <strong>{context.hotspot_ssid ?? 'INKPI'}</strong>
        <small>{context.wifi_qr_payload ? 'SCAN TO JOIN' : 'QR UNAVAILABLE'}</small>
      </div>
      {context.wifi_qr_payload && (
        <QRCodeSVG value={context.wifi_qr_payload} size={78} level="M" marginSize={0} />
      )}
    </div>
  )
}

function ContributionCalendar({ payload }: { payload: Record<string, unknown> | undefined }) {
  const counts = contributionCounts(payload)
  const today = startOfLocalDay(new Date())
  const days = Array.from({ length: 7 }, (_, index) => {
    const day = new Date(today)
    day.setDate(today.getDate() - (6 - index))
    const key = localDateKey(day)
    return { day, count: counts.get(key) ?? 0, today: index === 6 }
  })
  return (
    <div className="eink-calendar" aria-label="Last seven days of GitHub contributions">
      {days.map(({ day, count, today: isToday }) => (
        <div className={isToday ? 'today' : ''} key={localDateKey(day)}>
          <span>{day.toLocaleDateString('en-US', { weekday: 'narrow' })}</span>
          <i className={count === 0 ? 'empty' : count <= 3 ? 'hatched' : 'solid'} title={`${count} contributions`} />
        </div>
      ))}
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
  const remainingDays = Math.max(0, Math.floor((reset.getTime() - Date.now()) / 86_400_000))
  const clock = reset.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false })
  return `${remainingDays} ${remainingDays === 1 ? 'DAY' : 'DAYS'}, ${clock}`
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
