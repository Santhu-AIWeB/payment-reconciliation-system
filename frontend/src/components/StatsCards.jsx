function MetricCard({ label, value, helper, tone = 'neutral' }) {
  return (
    <div className={`metric-card ${tone}`}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      <div className="metric-helper">{helper}</div>
    </div>
  )
}

export default function StatsCards({ summary }) {
  if (!summary) return null

  const transactions = summary.transactions || {}
  const reconciliations = summary.reconciliations || {}

  return (
    <section className="metric-grid" aria-label="Payment health">
      <MetricCard
        label="Total transactions"
        value={transactions.total ?? 0}
        helper="All payment records"
        tone="neutral"
      />
      <MetricCard
        label="Matched"
        value={reconciliations.matched ?? 0}
        helper="Gateway and bank aligned"
        tone="positive"
      />
      <MetricCard
        label="Mismatches"
        value={reconciliations.mismatch ?? 0}
        helper="Require resolution"
        tone="danger"
      />
      <MetricCard
        label="Pending"
        value={reconciliations.pending ?? 0}
        helper="Awaiting a record or update"
        tone="warning"
      />
    </section>
  )
}
