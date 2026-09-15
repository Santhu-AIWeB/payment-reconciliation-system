const API_BASE = 'https://payment-reconciliation-system-k1ry.onrender.com'
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