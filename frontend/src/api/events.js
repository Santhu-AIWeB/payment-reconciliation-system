const API_BASE = 'http://localhost:8000'

export async function fetchEvents() {
  const response = await fetch(`${API_BASE}/api/events`)

  const data = await response.json()

  if (!response.ok) {
    throw new Error(
      data?.detail || 'Unable to load payment events.'
    )
  }

  return Array.isArray(data) ? data : []
}