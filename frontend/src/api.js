// In dev the backend runs on port 8000. When deployed, the API is served from
// the same origin, so a relative path is enough.
const BASE = import.meta.env.DEV ? 'http://localhost:8000' : ''

async function get(path, params = {}) {
  const query = new URLSearchParams(params).toString()
  const res = await fetch(`${BASE}${path}?${query}`)
  if (!res.ok) {
    throw new Error(`${path} returned ${res.status}`)
  }
  return res.json()
}

export const getConfig = () => get('/api/config')
export const getDay = (date, cutoff) => get('/api/day', { date, cutoff })
export const getSummary = (cutoff) => get('/api/summary', { cutoff })
export const getHourlyProfile = (cutoff) => get('/api/hourly-profile', { cutoff })
