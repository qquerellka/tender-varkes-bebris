import type { AuthSession } from '@shared/api/search'

export const PORTAL_SESSION_STORAGE_KEY = 'portal-demo-session-v2'
export const PORTAL_LAST_SEARCH_SESSION_STORAGE_KEY = 'portal-last-search-session-v2'

export function readStoredSession(): AuthSession | null {
  if (typeof window === 'undefined') {
    return null
  }

  const rawValue = window.localStorage.getItem(PORTAL_SESSION_STORAGE_KEY)
  if (!rawValue) {
    return null
  }

  try {
    return JSON.parse(rawValue) as AuthSession
  } catch {
    return null
  }
}

export function writeStoredSession(session: AuthSession) {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.setItem(PORTAL_SESSION_STORAGE_KEY, JSON.stringify(session))
}

export function clearStoredSession() {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.removeItem(PORTAL_SESSION_STORAGE_KEY)
  window.localStorage.removeItem(PORTAL_LAST_SEARCH_SESSION_STORAGE_KEY)
}

export function readLastSearchSessionId(): string | null {
  if (typeof window === 'undefined') {
    return null
  }

  return window.localStorage.getItem(PORTAL_LAST_SEARCH_SESSION_STORAGE_KEY)
}

export function writeLastSearchSessionId(sessionId: string) {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.setItem(PORTAL_LAST_SEARCH_SESSION_STORAGE_KEY, sessionId)
}
