/**
 * One place that knows how to talk to the backend.
 *
 * Every network call goes through `request()`, so the token header, error
 * handling and base URL live in exactly one file. If the API moves, one line
 * changes.
 */

// Where API calls go:
// - Production build (Vercel): '' - the browser calls /api/... on the site's own
//   address and frontend/vercel.json forwards it to the API project. One origin,
//   so the browser never makes a cross-site (CORS) request.
// - `npm run dev`: VITE_API_URL if set, otherwise the local backend on port 8000.
const BASE = import.meta.env.PROD
  ? ''
  : (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000')

const TOKEN_KEY = 'dinesense_token'

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null // private browsing can throw on access
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* ignore - the app still works for this session, it just will not persist */
  }
}

/** Thrown for any non-2xx response, carrying the status so callers can branch. */
export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request(path, { method = 'GET', body, auth = true, isForm = false } = {}) {
  const headers = {}
  if (!isForm) headers['Content-Type'] = 'application/json'

  const token = getToken()
  if (auth && token) headers.Authorization = `Bearer ${token}`

  let response
  try {
    response = await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: isForm ? body : body ? JSON.stringify(body) : undefined,
    })
  } catch {
    // fetch only rejects on network failure, not on 4xx/5xx
    throw new ApiError(
      'Cannot reach the API. Is the backend running on ' + (BASE || window.location.origin) + '?',
      0,
    )
  }

  if (response.status === 401) {
    setToken(null)
    throw new ApiError('Your session has expired. Please log in again.', 401)
  }

  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const data = await response.json()
      if (typeof data.detail === 'string') {
        detail = data.detail
      } else if (Array.isArray(data.detail)) {
        // FastAPI validation errors arrive as a list of field problems
        detail = data.detail
          .map((e) => `${e.loc?.slice(1).join('.') || 'field'}: ${e.msg}`)
          .join('; ')
      }
    } catch {
      /* response had no JSON body - keep the generic message */
    }
    throw new ApiError(detail, response.status)
  }

  if (response.status === 204) return null
  return response.json()
}

function query(params = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      search.append(key, value)
    }
  })
  const string = search.toString()
  return string ? `?${string}` : ''
}

export const api = {
  // ---- auth
  login: (email, password) =>
    request('/api/auth/login', { method: 'POST', body: { email, password }, auth: false }),
  me: () => request('/api/auth/me'),
  listUsers: () => request('/api/auth/users'),
  createUser: (payload) => request('/api/auth/users', { method: 'POST', body: payload }),

  // ---- restaurants
  listRestaurants: () => request('/api/restaurants'),
  createRestaurant: (payload) =>
    request('/api/restaurants', { method: 'POST', body: payload }),
  listBranches: (restaurantId) => request(`/api/restaurants/${restaurantId}/branches`),
  createBranch: (restaurantId, payload) =>
    request(`/api/restaurants/${restaurantId}/branches`, { method: 'POST', body: payload }),

  // ---- reviews
  analyse: (reviewText) =>
    request('/api/reviews/analyse', {
      method: 'POST',
      body: { review_text: reviewText },
      auth: false,
    }),
  submitReview: (payload) =>
    request('/api/reviews', { method: 'POST', body: payload, auth: false }),
  listReviews: (params) => request(`/api/reviews${query(params)}`),
  uploadCsv: (restaurantId, file, branchId) => {
    const form = new FormData()
    form.append('file', file)
    return request(
      `/api/reviews/batch${query({ restaurant_id: restaurantId, branch_id: branchId })}`,
      { method: 'POST', body: form, isForm: true },
    )
  },

  // ---- analytics
  summary: (params) => request(`/api/analytics/summary${query(params)}`),
  trends: (params) => request(`/api/analytics/trends${query(params)}`),
  aspects: (params) => request(`/api/analytics/aspects${query(params)}`),
  branches: (params) => request(`/api/analytics/branches${query(params)}`),
  alerts: (params) => request(`/api/alerts${query(params)}`),
  modelMetrics: () => request('/api/model/metrics', { auth: false }),
  health: () => request('/health', { auth: false }),
}
