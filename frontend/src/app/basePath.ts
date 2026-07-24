export type AppRoute = '/' | '/todo' | '/pages' | '/settings'

export function appBasePath(pathname: string): '' | '/inkpi' {
  return pathname === '/inkpi' || pathname.startsWith('/inkpi/') ? '/inkpi' : ''
}

export function routeFromPathname(pathname: string): AppRoute {
  const base = appBasePath(pathname)
  const route = pathname.slice(base.length) || '/'
  return route === '/todo' || route === '/pages' || route === '/settings' ? route : '/'
}

export function appPath(route: AppRoute, pathname = window.location.pathname): string {
  return `${appBasePath(pathname)}${route}` || '/'
}
