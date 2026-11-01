/**
 * Minimal fetch wrapper for the QueueWise API. Session-cookie auth with a
 * CSRF token header on unsafe methods; consistent error surfacing.
 */

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'))
  return match ? decodeURIComponent(match[1]) : null
}

export class ApiError extends Error {
  status: number
  data: unknown

  constructor(status: number, data: unknown) {
    const message =
      data && typeof data === 'object' && 'detail' in data
        ? String((data as { detail: unknown }).detail)
        : typeof data === 'object' && data !== null
          ? Object.values(data as Record<string, unknown[]>).flat().join(', ') ||
            'Request failed'
          : 'Request failed'
    super(message)
    this.status = status
    this.data = data
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  let payload: BodyInit | undefined

  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const csrf = getCookie('csrftoken')
    if (csrf) headers['X-CSRFToken'] = csrf
  }

  const response = await fetch(path, {
    method,
    headers,
    body: payload,
    credentials: 'same-origin',
  })

  if (response.status === 204) return undefined as T
  const contentType = response.headers.get('Content-Type') ?? ''
  const text = await response.text()

  let data: unknown
  if (text === '') {
    data = {}
  } else if (contentType.includes('application/json')) {
    try {
      data = JSON.parse(text)
    } catch {
      // Malformed JSON from the server: surface the body, not a parse error.
      data = { detail: text.slice(0, 200) }
    }
  } else {
    // Non-JSON error body (e.g. a server or proxy failure page). Keep the
    // server's own first line — e.g. "OperationalError at /api/..." — so the
    // original failure stays visible instead of becoming a parse error.
    const firstLine = text.split('\n', 1)[0].trim().slice(0, 200)
    data = {
      detail: firstLine
        ? `${firstLine} (server error — the service may be temporarily unavailable)`
        : `Unexpected ${response.status} response from the server`,
    }
  }

  if (!response.ok) {
    // A 401 on an app page means the session is gone (expired, or signed
    // out in another tab/browser). Send the user to login with a clean
    // cache instead of letting them act on a dead session. Login/register
    // failures are excluded — they show their own error message.
    if (
      response.status === 401 &&
      !path.startsWith('/api/auth/') &&
      typeof window !== 'undefined' &&
      !['/login', '/register', '/'].includes(window.location.pathname)
    ) {
      import('../queryClient').then(({ queryClient }) => queryClient.clear())
      window.location.assign('/login')
    }
    throw new ApiError(response.status, data)
  }
  return data as T
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body ?? {}),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body ?? {}),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body ?? {}),
  delete: <T>(path: string) => request<T>('DELETE', path),
}
