const toneMap = {
  success: 'success',
  debited: 'success',
  completed: 'success',
  matched: 'success',
  failed: 'danger',
  mismatch: 'danger',
  not_debited: 'danger',
  timeout: 'warning',
  delayed: 'warning',
  pending: 'warning',
  refund: 'info',
  retry: 'violet',
  investigate: 'orange',
  wait: 'teal',
  block: 'danger',
  duplicate: 'violet',
  processing: 'warning',
  initiated: 'info',
  max_attempts_reached: 'danger',
}

export default function StatusBadge({ value }) {
  if (!value) return <span className="badge muted">—</span>

  const key = String(value).toLowerCase().replace(/\s+/g, '_')
  const tone = toneMap[key] || 'neutral'

  return <span className={`badge ${tone}`}>{String(value).replaceAll('_', ' ')}</span>
}
