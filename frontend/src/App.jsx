import { useCallback, useEffect, useMemo, useState } from 'react'
import './index.css'
import './ai_investigations_drawer.css'

import Sidebar from './components/Sidebar'
import StatsCards from './components/StatsCards'
import StatusBadge from './components/StatusBadge'
import TransactionsTable from './components/TransactionsTable'
import TransactionDetail from './components/TransactionDetail'
import { fetchSummary, fetchTransactions } from './api/dashboard'
import EventOperationsPage from './pages/EventOperationsPage'

function fmtAmount(amount, currency = 'INR') {
  if (amount == null) return '—'

  const symbol = currency === 'INR' ? '₹' : `${currency} `

  return `${symbol}${Number(amount).toLocaleString('en-IN', {
    minimumFractionDigits: 2,
  })}`
}

function formatDate(dateStr) {
  if (!dateStr) return '—'

  return new Date(dateStr).toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  })
}

function PageHeader({
  title,
  subtitle,
  onRefresh,
  spinning,
}) {
  const lastUpdated = new Date().toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  })

  return (
    <header className="content-header">

      <div className="content-header-left">

        {/* Breadcrumb */}
        <div className="header-breadcrumb">
          <span>PayReconcile</span>
          <span className="breadcrumb-separator">/</span>
          <span className="breadcrumb-current">
            {title}
          </span>
        </div>

        {/* Main title */}
        <h1>{title}</h1>

        {/* Subtitle */}
        <p>{subtitle}</p>

        {/* Last updated */}
        <div className="last-updated">
          Last updated {lastUpdated}
        </div>

      </div>

      <div className="header-actions">

        {/* Connection status */}
        <div className="connection-pill">
          <span className="status-dot" />
          <span className="connection-label">
            LIVE
          </span>
          {/* <span className="connection-text">
            Backend connected
          </span> */}
        </div>

        {/* Refresh */}
        <button
          type="button"
          className={`refresh-button ${
            spinning ? 'spinning' : ''
          }`}
          onClick={onRefresh}
        >
          <span className="refresh-icon">
            ↻
          </span>

          <span>
            {spinning
              ? 'Syncing…'
              : 'Refresh'}
          </span>
        </button>

      </div>

    </header>
  )
}

function AttentionSection({ summary, onNavigate }) {
  const actions = [
    {
      key: 'refund',
      label: 'Refund required',
      count: summary?.actions_required?.refund ?? 0,
      copy: 'Payments where bank debited but gateway failed',
      tone: 'danger',
      target: 'refunds',
    },
    {
      key: 'retry',
      label: 'Retry required',
      count: summary?.actions_required?.retry ?? 0,
      copy: 'Payments needing another simulated attempt',
      tone: 'violet',
      target: 'retries',
    },
    {
      key: 'investigate',
      label: 'Investigation',
      count: summary?.actions_required?.investigate ?? 0,
      copy: 'Unexpected or ambiguous payment states',
      tone: 'orange',
      target: 'investigations',
    },
    {
      key: 'wait',
      label: 'Awaiting update',
      count: summary?.actions_required?.wait ?? 0,
      copy: 'Gateway or bank state is still pending',
      tone: 'warning',
      target: 'reconciliation',
    },
  ]

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <div className="panel-title">Requires attention</div>
          <div className="panel-subtitle">
            Exceptions and operational work queues
          </div>
        </div>
      </div>

      <div className="attention-grid">
        {actions.map(action => (
          <button
            type="button"
            className={`attention-card ${action.tone}`}
            key={action.key}
            onClick={() => onNavigate(action.target)}
          >
            <div className="attention-top">
              <span>{action.label}</span>
              <span className="attention-arrow">→</span>
            </div>

            <div className="attention-count">{action.count}</div>

            <div className="attention-copy">{action.copy}</div>
          </button>
        ))}
      </div>
    </section>
  )
}

function SearchFilters({ search, setSearch, filter, setFilter }) {
  return (
    <div className="toolbar">
      <div className="search-wrap">
        <span className="search-icon">⌕</span>

        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search transaction ID..."
          aria-label="Search transaction ID"
        />

        {search && (
          <button
            type="button"
            className="clear-search"
            onClick={() => setSearch('')}
            aria-label="Clear search"
          >
            ×
          </button>
        )}
      </div>

      <select
        value={filter}
        onChange={e => setFilter(e.target.value)}
        aria-label="Filter transactions"
      >
        <option value="ALL">All statuses</option>
        <option value="MATCHED">Matched</option>
        <option value="MISMATCH">Mismatch</option>
        <option value="PENDING">Pending</option>
        <option value="REFUND">Refund</option>
        <option value="RETRY">Retry</option>
        <option value="INVESTIGATE">Investigate</option>
      </select>

      {(search || filter !== 'ALL') && (
        <button
          type="button"
          className="text-button"
          onClick={() => {
            setSearch('')
            setFilter('ALL')
          }}
        >
          Clear filters
        </button>
      )}
    </div>
  )
}

function PageSectionHeading({ title, subtitle, count }) {
  return (
    <div className="section-heading-large">
      <div>
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>

      <span className="record-count">{count} records</span>
    </div>
  )
}

function TransactionsPage({ transactions, onSelect }) {
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('ALL')

  const filtered = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase()

    return (transactions || []).filter(txn => {
      const transactionId = txn.transaction_id?.toLowerCase() || ''

      const idMatch =
        !normalizedSearch ||
        transactionId.includes(normalizedSearch)

      if (!idMatch) return false

      if (filter === 'MATCHED') {
        return txn.reconciliation?.reconciliation_status === 'MATCHED'
      }

      if (filter === 'MISMATCH') {
        return txn.reconciliation?.reconciliation_status === 'MISMATCH'
      }

      if (filter === 'PENDING') {
        return txn.reconciliation?.reconciliation_status === 'PENDING'
      }

      if (filter === 'REFUND') {
        return txn.reconciliation?.action_required === 'REFUND'
      }

      if (filter === 'RETRY') {
        return txn.reconciliation?.action_required === 'RETRY'
      }

      if (filter === 'INVESTIGATE') {
        return txn.reconciliation?.action_required === 'INVESTIGATE'
      }

      return true
    })
  }, [transactions, search, filter])

  return (
    <section className="page-section">
      <PageSectionHeading
        title="Transactions"
        subtitle="Search and inspect payment lifecycles"
        count={filtered.length}
      />

      <SearchFilters
        search={search}
        setSearch={setSearch}
        filter={filter}
        setFilter={setFilter}
      />

      <div className="panel">
        <TransactionsTable
          transactions={filtered}
          onSelect={onSelect}
        />
      </div>
    </section>
  )
}

function ReconciliationPage({ transactions, onSelect }) {
  const data = (transactions || []).filter(txn => txn.reconciliation)

  const stats = {
    matched: data.filter(txn => txn.reconciliation?.reconciliation_status === 'MATCHED').length,
    mismatch: data.filter(txn => txn.reconciliation?.reconciliation_status === 'MISMATCH').length,
    pending: data.filter(txn => txn.reconciliation?.reconciliation_status === 'PENDING').length,
  }

  return (
    <section className="page-section reconciliation-page">
      <PageSectionHeading
        title="Reconciliation"
        subtitle="Compare gateway and bank outcomes"
        count={data.length}
      />

      <div className="recon-stat-grid">
        <div className="recon-stat-card matched">
          <div className="recon-stat-label">Matched</div>
          <div className="recon-stat-value">{stats.matched}</div>
          <div className="recon-stat-copy">Gateway and bank agree</div>
        </div>

        <div className="recon-stat-card mismatch">
          <div className="recon-stat-label">Mismatch</div>
          <div className="recon-stat-value">{stats.mismatch}</div>
          <div className="recon-stat-copy">Require exception handling</div>
        </div>

        <div className="recon-stat-card pending">
          <div className="recon-stat-label">Pending</div>
          <div className="recon-stat-value">{stats.pending}</div>
          <div className="recon-stat-copy">Awaiting definitive outcome</div>
        </div>

        <div className="recon-stat-card total">
          <div className="recon-stat-label">Total records</div>
          <div className="recon-stat-value">{data.length}</div>
          <div className="recon-stat-copy">Transactions with reconciliation data</div>
        </div>
      </div>

      <div className="panel recon-panel">
        <div className="panel-header recon-panel-header">
          <div>
            <div className="panel-title">Reconciliation records</div>
            <div className="panel-subtitle">
              Click a row to inspect the complete transaction lifecycle
            </div>
          </div>
          <span className="recon-hint">Select a transaction →</span>
        </div>

        <div className="table-wrap">
          <table className="ops-table recon-table">
            <thead>
              <tr>
                <th>Transaction</th>
                <th>Gateway</th>
                <th>Bank</th>
                <th>Reconciliation</th>
                <th>Reason</th>
                <th>Action</th>
                <th>Created</th>
              </tr>
            </thead>

            <tbody>
              {data.map(txn => {
                const reconStatus = txn.reconciliation?.reconciliation_status
                const action = txn.reconciliation?.action_required

                return (
                  <tr
                    key={txn.transaction_id}
                    onClick={() => onSelect(txn.transaction_id)}
                    className={`recon-row recon-row-${(reconStatus || 'pending').toLowerCase()}`}
                  >
                    <td>
                      <div className="recon-txn-cell">
                        <div className="recon-txn-id mono">
                          {txn.transaction_id}
                        </div>
                        <div className="recon-txn-amount">
                          {fmtAmount(txn.amount, txn.currency)}
                        </div>
                      </div>
                    </td>

                    <td>
                      <StatusBadge value={txn.gateway?.status} />
                    </td>

                    <td>
                      <StatusBadge value={txn.bank?.status} />
                    </td>

                    <td>
                      <StatusBadge value={reconStatus} />
                    </td>

                    <td className="reason-cell recon-reason">
                      {txn.reconciliation?.reason || '—'}
                    </td>

                    <td>
                      <StatusBadge value={action} />
                    </td>

                    <td className="time-cell">
                      {formatDate(txn.reconciliation?.created_at)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {!data.length && (
          <div className="empty-state compact">
            <div className="empty-title">
              No reconciliation records
            </div>
            <div className="empty-copy">
              Process a transaction through the reconciliation engine to see it here.
            </div>
          </div>
        )}
      </div>
    </section>
  )
}

function RefundsPage({ transactions, onSelect }) {
  const refundCases = (transactions || []).filter(
    txn =>
      txn.reconciliation?.action_required === 'REFUND' ||
      txn.refund
  )

  const pendingRefunds = refundCases.filter(txn => !txn.refund)
  const processedRefunds = refundCases.filter(txn => txn.refund)

  const stats = {
    required: pendingRefunds.length,
    initiated: processedRefunds.filter(
      txn => txn.refund?.status === 'INITIATED'
    ).length,
    processing: processedRefunds.filter(
      txn => txn.refund?.status === 'PROCESSING'
    ).length,
    completed: processedRefunds.filter(
      txn => txn.refund?.status === 'COMPLETED'
    ).length,
    failed: processedRefunds.filter(
      txn => txn.refund?.status === 'FAILED'
    ).length,
  }

  const totalRefundAmount = refundCases.reduce(
    (sum, txn) =>
      sum +
      Number(
        txn.refund?.amount ??
        (txn.reconciliation?.action_required === 'REFUND'
          ? txn.amount
          : 0)
      ),
    0
  )

  const currency = refundCases[0]?.currency || 'INR'

  return (
    <section className="page-section refunds-page">
      <PageSectionHeading
        title="Refunds"
        subtitle="Track refund-required cases and simulated refund resolution"
        count={refundCases.length}
      />

      <div className="refund-stat-grid">
        <div className="refund-stat-card initiated">
          <div className="refund-stat-label">Refund required</div>
          <div className="refund-stat-value">{stats.required}</div>
          <div className="refund-stat-copy">Eligible mismatch cases</div>
        </div>

        <div className="refund-stat-card processing">
          <div className="refund-stat-label">Processing</div>
          <div className="refund-stat-value">{stats.processing}</div>
          <div className="refund-stat-copy">Awaiting completion</div>
        </div>

        <div className="refund-stat-card completed">
          <div className="refund-stat-label">Completed</div>
          <div className="refund-stat-value">{stats.completed}</div>
          <div className="refund-stat-copy">Successfully resolved</div>
        </div>

        <div className="refund-stat-card failed">
          <div className="refund-stat-label">Failed</div>
          <div className="refund-stat-value">{stats.failed}</div>
          <div className="refund-stat-copy">Need attention</div>
        </div>
      </div>

      <div className="refund-overview-card">
        <div>
          <div className="refund-overview-label">Total simulated refund value</div>
          <div className="refund-overview-value">
            {fmtAmount(totalRefundAmount, currency)}
          </div>
        </div>

        <div className="refund-overview-meta">
          <span className="refund-overview-dot" />
          <span>{refundCases.length} refund cases</span>
        </div>
      </div>

      <div className="panel refund-panel">
        <div className="panel-header refund-panel-header">
          <div>
            <div className="panel-title">Refund cases</div>
            <div className="panel-subtitle">
              Eligible refund cases and processed refund records
            </div>
          </div>
          <span className="refund-hint">Select a transaction →</span>
        </div>

        <div className="table-wrap">
          <table className="ops-table refund-table">
            <thead>
              <tr>
                <th>Transaction</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Reason</th>
                <th>Refund reference</th>
                <th>Created</th>
                <th>Completed</th>
              </tr>
            </thead>

            <tbody>
              {refundCases.map(txn => {
                const status =
                  txn.refund?.status || 'REFUND_REQUIRED'

                return (
                  <tr
                    key={txn.transaction_id}
                    onClick={() => onSelect(txn.transaction_id)}
                    className={`refund-row refund-row-${status.toLowerCase()}`}
                  >
                    <td>
                      <div className="refund-txn-cell">
                        <div className="refund-txn-id mono">
                          {txn.transaction_id}
                        </div>
                        <div className="refund-txn-status">
                          Original payment: {txn.status || '—'}
                        </div>
                      </div>
                    </td>

                    <td className="amount-cell">
                      {fmtAmount(
                        txn.refund?.amount ?? txn.amount,
                        txn.currency
                      )}
                    </td>

                    <td>
                      <StatusBadge value={status} />
                    </td>

                    <td className="reason-cell refund-reason">
                      {txn.refund?.reason ||
                        txn.reconciliation?.reason ||
                        '—'}
                    </td>

                    <td className="mono">
                      {txn.refund?.refund_reference || '—'}
                    </td>

                    <td className="time-cell">
                      {formatDate(
                        txn.refund?.created_at ||
                        txn.reconciliation?.created_at
                      )}
                    </td>

                    <td className="time-cell">
                      {formatDate(txn.refund?.completed_at)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {!refundCases.length && (
          <div className="empty-state compact">
            <div className="empty-title">No refund cases</div>
            <div className="empty-copy">
              Transactions requiring refunds will appear here.
            </div>
          </div>
        )}
      </div>
    </section>
  )
}

function RetriesPage({ transactions, onSelect }) {
  const [attempts, setAttempts] = useState([])
  const [loadingRetries, setLoadingRetries] = useState(false)
  const [retryError, setRetryError] = useState(null)

  const loadRetryAttempts = useCallback(async () => {
    setLoadingRetries(true)
    setRetryError(null)

    try {
      const response = await fetch(
        'http://localhost:8000/api/retry/attempts'
      )
      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          data?.detail || 'Unable to load retry attempts.'
        )
      }

      setAttempts(Array.isArray(data) ? data : [])
    } catch (err) {
      setRetryError(
        err?.message ||
          'Unable to connect to the retry attempts endpoint.'
      )
    } finally {
      setLoadingRetries(false)
    }
  }, [])

  useEffect(() => {
    loadRetryAttempts()
  }, [loadRetryAttempts])

  const eligibleRetries = (transactions || []).filter(
    txn => txn.reconciliation?.action_required === 'RETRY'
  )

  const stats = {
    required: eligibleRetries.length,
    initiated: attempts.filter(item => item.status === 'INITIATED').length,
    processing: attempts.filter(item => item.status === 'PROCESSING').length,
    success: attempts.filter(item => item.status === 'SUCCESS').length,
    failed: attempts.filter(item =>
      ['FAILED', 'MAX_ATTEMPTS_REACHED'].includes(item.status)
    ).length,
  }

  const maxedOut = attempts.filter(
    item =>
      item.status === 'MAX_ATTEMPTS_REACHED' ||
      Number(item.attempt_number || 0) >= 3
  ).length

  return (
    <section className="page-section retries-page">
      <PageSectionHeading
        title="Retries"
        subtitle="Track retry-required cases and simulated retry attempts"
        count={eligibleRetries.length + attempts.length}
      />

      <div className="retry-stat-grid">
        <div className="retry-stat-card initiated">
          <div className="retry-stat-label">Retry required</div>
          <div className="retry-stat-value">{stats.required}</div>
          <div className="retry-stat-copy">Eligible payment exceptions</div>
        </div>

        <div className="retry-stat-card processing">
          <div className="retry-stat-label">Processing</div>
          <div className="retry-stat-value">{stats.processing}</div>
          <div className="retry-stat-copy">Currently being simulated</div>
        </div>

        <div className="retry-stat-card success">
          <div className="retry-stat-label">Successful</div>
          <div className="retry-stat-value">{stats.success}</div>
          <div className="retry-stat-copy">Recovered payment attempts</div>
        </div>

        <div className="retry-stat-card failed">
          <div className="retry-stat-label">Failed</div>
          <div className="retry-stat-value">{stats.failed}</div>
          <div className="retry-stat-copy">Need attention or review</div>
        </div>
      </div>

      <div className="retry-limit-card">
        <div>
          <div className="retry-limit-label">Retry safety limit</div>
          <div className="retry-limit-title">
            Maximum 3 attempts per transaction
          </div>
          <div className="retry-limit-copy">
            The workflow prevents repeated retry attempts beyond the configured limit.
          </div>
        </div>

        <div className="retry-limit-badge">
          <span>{maxedOut}</span>
          <small>at limit</small>
        </div>
      </div>

      {retryError && (
        <div className="error-banner" style={{ marginBottom: 14 }}>
          <span>{retryError}</span>
          <button type="button" onClick={loadRetryAttempts}>
            Retry
          </button>
        </div>
      )}

      <div className="panel retry-panel">
        <div className="panel-header retry-panel-header">
          <div>
            <div className="panel-title">Retry required</div>
            <div className="panel-subtitle">
              Transactions eligible for a simulated retry
            </div>
          </div>
          <span className="retry-hint">
            {eligibleRetries.length} eligible
          </span>
        </div>

        <div className="table-wrap">
          <table className="ops-table retry-table">
            <thead>
              <tr>
                <th>Transaction</th>
                <th>Amount</th>
                <th>Gateway</th>
                <th>Bank</th>
                <th>Reconciliation</th>
                <th>Reason</th>
              </tr>
            </thead>

            <tbody>
              {eligibleRetries.map(txn => (
                <tr
                  key={`eligible-${txn.transaction_id}`}
                  onClick={() => onSelect(txn.transaction_id)}
                >
                  <td>
                    <div className="retry-txn-cell">
                      <div className="retry-txn-id mono">
                        {txn.transaction_id}
                      </div>
                      <div className="retry-txn-status">
                        Payment status: {txn.status || '—'}
                      </div>
                    </div>
                  </td>

                  <td className="amount-cell">
                    {fmtAmount(txn.amount, txn.currency)}
                  </td>

                  <td>
                    <StatusBadge value={txn.gateway?.status} />
                  </td>

                  <td>
                    <StatusBadge value={txn.bank?.status} />
                  </td>

                  <td>
                    <StatusBadge value="RETRY_REQUIRED" />
                  </td>

                  <td className="reason-cell retry-reason">
                    {txn.reconciliation?.reason || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {!eligibleRetries.length && (
          <div className="empty-state compact">
            <div className="empty-title">No retry-required cases</div>
            <div className="empty-copy">
              Transactions requiring a retry will appear here.
            </div>
          </div>
        )}
      </div>

      <div className="panel retry-panel">
        <div className="panel-header retry-panel-header">
          <div>
            <div className="panel-title">Retry attempts</div>
            <div className="panel-subtitle">
              Click a transaction to inspect every processed attempt
            </div>
          </div>
          <span className="retry-hint">
            {loadingRetries ? 'Loading…' : 'Select a transaction →'}
          </span>
        </div>

        <div className="table-wrap">
          <table className="ops-table retry-table">
            <thead>
              <tr>
                <th>Transaction</th>
                <th>Attempt</th>
                <th>Retry reference</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Reason</th>
                <th>Created</th>
                <th>Completed</th>
              </tr>
            </thead>

            <tbody>
              {attempts.map(attempt => {
                const attemptNumber = Number(attempt.attempt_number || 0)
                const isLastAttempt = attemptNumber >= 3

                return (
                  <tr
                    key={`${attempt.transaction_id}-${attempt.attempt_number}-${attempt.retry_reference}`}
                    onClick={() => onSelect(attempt.transaction_id)}
                    className={`retry-row retry-row-${String(
                      attempt.status || 'UNKNOWN'
                    ).toLowerCase()}`}
                  >
                    <td>
                      <div className="retry-txn-cell">
                        <div className="retry-txn-id mono">
                          {attempt.transaction_id}
                        </div>
                        <div className="retry-txn-status">
                          Payment status: {attempt.transaction_status || '—'}
                        </div>
                      </div>
                    </td>

                    <td>
                      <div className={`attempt-pill ${isLastAttempt ? 'limit' : ''}`}>
                        <strong>{attemptNumber}</strong>
                        <span>/ 3</span>
                      </div>
                    </td>

                    <td className="mono">
                      {attempt.retry_reference || '—'}
                    </td>

                    <td className="amount-cell">
                      {fmtAmount(attempt.amount, attempt.currency)}
                    </td>

                    <td>
                      <StatusBadge value={attempt.status} />
                    </td>

                    <td className="reason-cell retry-reason">
                      {attempt.reason || '—'}
                    </td>

                    <td className="time-cell">
                      {formatDate(attempt.created_at)}
                    </td>

                    <td className="time-cell">
                      {formatDate(attempt.completed_at)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {!loadingRetries && !attempts.length && (
          <div className="empty-state compact">
            <div className="empty-title">
              No retry attempts have been recorded
            </div>
            <div className="empty-copy">
              Eligible retry cases are shown above. Process a retry to create an attempt record.
            </div>
          </div>
        )}
      </div>
    </section>
  )
}

function AIAnalysisDrawer({ analysis, transaction, loading, error, onClose, onOpenTransaction, onAnalyze }) {
  if (!analysis && !loading && !error) return null

  const riskLevel = analysis?.risk_level || '—'
  const riskScore =
    typeof analysis?.risk_score === 'number'
      ? analysis.risk_score.toFixed(4)
      : '—'

  return (
    <div className="ai-drawer-backdrop" onClick={onClose}>
      <aside
        className="ai-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="AI risk analysis"
        onClick={event => event.stopPropagation()}
      >
        <div className="ai-drawer-header">
          <div>
            <div className="ai-drawer-eyebrow">AI ASSIST</div>
            <h3>Risk analysis</h3>
            <div className="ai-drawer-transaction mono">
              {analysis?.transaction_id || transaction?.transaction_id || 'Transaction'}
            </div>
          </div>

          <button
            type="button"
            className="ai-drawer-close"
            onClick={onClose}
            aria-label="Close AI analysis"
          >
            ×
          </button>
        </div>

        {loading && (
          <div className="ai-drawer-loading">
            <div className="ai-spinner" />
            <div>
              <strong>Analyzing transaction</strong>
              <span>Building a risk assessment from payment signals…</span>
            </div>
          </div>
        )}

        {error && (
          <div className="ai-drawer-error">
            <div className="ai-error-title">Analysis unavailable</div>
            <div className="ai-error-copy">{error}</div>
            <button
              type="button"
              className="ai-retry-button"
              onClick={() => onAnalyze(transaction?.transaction_id)}
            >
              Try again
            </button>
          </div>
        )}

        {analysis && !loading && (
          <>
            <div className={`ai-risk-banner ai-risk-${String(riskLevel).toLowerCase()}`}>
              <div>
                <span className="ai-risk-label">Risk level</span>
                <strong>{riskLevel}</strong>
              </div>
              <div className="ai-score-block">
                <span>Risk score</span>
                <strong>{riskScore}</strong>
              </div>
            </div>

            <div className="ai-drawer-section">
              <div className="ai-section-label">Priority</div>
              <div className="ai-priority">
                {analysis.investigation_priority || 'No immediate investigation required'}
              </div>
            </div>

            <div className="ai-drawer-section">
              <div className="ai-section-label">Why was it flagged?</div>
              <div className="ai-reason-list">
                {(analysis.reasons || ['No additional explanation returned.']).map((reason, index) => (
                  <div className="ai-reason-row" key={`${reason}-${index}`}>
                    <span className="ai-reason-dot" />
                    <span>{reason}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="ai-metrics-grid">
              <div className="ai-metric">
                <span>Model</span>
                <strong>{analysis.model_type || '—'}</strong>
              </div>
              <div className="ai-metric">
                <span>Training samples</span>
                <strong>{analysis.training_samples ?? '—'}</strong>
              </div>
              <div className="ai-metric">
                <span>Amount</span>
                <strong>{fmtAmount(transaction?.amount, transaction?.currency)}</strong>
              </div>
              <div className="ai-metric">
                <span>Reconciliation</span>
                <strong>{transaction?.reconciliation?.reconciliation_status || '—'}</strong>
              </div>
            </div>

            <div className="ai-drawer-section">
              <div className="ai-section-label">Payment signals</div>
              <div className="ai-signal-list">
                <div className={`ai-signal ${analysis.features?.gateway_failed ? 'active' : ''}`}>
                  <span>Gateway failed</span>
                  <strong>{analysis.features?.gateway_failed ? 'Yes' : 'No'}</strong>
                </div>
                <div className={`ai-signal ${analysis.features?.gateway_timeout ? 'active' : ''}`}>
                  <span>Gateway timeout</span>
                  <strong>{analysis.features?.gateway_timeout ? 'Yes' : 'No'}</strong>
                </div>
                <div className={`ai-signal ${analysis.features?.bank_debited ? 'active' : ''}`}>
                  <span>Bank debited</span>
                  <strong>{analysis.features?.bank_debited ? 'Yes' : 'No'}</strong>
                </div>
                <div className={`ai-signal ${analysis.features?.bank_delayed ? 'active' : ''}`}>
                  <span>Bank delayed</span>
                  <strong>{analysis.features?.bank_delayed ? 'Yes' : 'No'}</strong>
                </div>
              </div>
            </div>

            <div className="ai-drawer-footer">
              <div className="ai-disclaimer">
                AI provides analysis only. Existing refund, retry and investigation workflows remain in control.
              </div>

              <div className="ai-drawer-actions">
                <button
                  type="button"
                  className="ai-secondary-button"
                  onClick={() => onAnalyze(analysis.transaction_id)}
                >
                  Re-analyze
                </button>

                <button
                  type="button"
                  className="ai-primary-button"
                  onClick={() => onOpenTransaction(analysis.transaction_id)}
                >
                  Open transaction →
                </button>
              </div>
            </div>
          </>
        )}
      </aside>
    </div>
  )
}

function InvestigationsPage({ transactions, onSelect }) {
  const [analysis, setAnalysis] = useState(null)
  const [analysisTarget, setAnalysisTarget] = useState(null)
  const [analysisLoading, setAnalysisLoading] = useState(false)
  const [analysisError, setAnalysisError] = useState(null)

  const rows = (transactions || []).filter(txn =>
    txn.reconciliation?.action_required === 'INVESTIGATE' ||
    txn.status === 'MANUAL_REVIEW'
  )

  const stats = {
    open: rows.filter(txn => txn.status === 'MANUAL_REVIEW').length,
    investigate: rows.filter(
      txn => txn.reconciliation?.action_required === 'INVESTIGATE'
    ).length,
    mismatch: rows.filter(
      txn => txn.reconciliation?.reconciliation_status === 'MISMATCH'
    ).length,
  }

  const runAnalysis = async transactionId => {
    if (!transactionId) return

    const transaction = rows.find(item => item.transaction_id === transactionId) || null
    setAnalysisTarget(transaction)
    setAnalysis(null)
    setAnalysisError(null)
    setAnalysisLoading(true)

    try {
      const response = await fetch(
        `http://localhost:8000/api/ai/analyze/${encodeURIComponent(transactionId)}`
      )

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data?.detail || 'AI analysis failed.')
      }

      setAnalysis(data)
    } catch (err) {
      setAnalysisError(
        err?.message || 'Unable to connect to the AI analysis endpoint.'
      )
    } finally {
      setAnalysisLoading(false)
    }
  }

  const closeAnalysis = () => {
    setAnalysis(null)
    setAnalysisTarget(null)
    setAnalysisError(null)
    setAnalysisLoading(false)
  }

  const openTransactionFromAI = transactionId => {
    closeAnalysis()
    onSelect(transactionId)
  }

  return (
    <>
      <section className="page-section investigations-page">
        <PageSectionHeading
          title="Investigations"
          subtitle="Review transactions that need manual attention"
          count={rows.length}
        />

        <div className="investigation-stat-grid">
          <div className="investigation-stat-card open">
            <div className="investigation-stat-label">Manual review</div>
            <div className="investigation-stat-value">{stats.open}</div>
            <div className="investigation-stat-copy">Transactions marked for review</div>
          </div>

          <div className="investigation-stat-card investigate">
            <div className="investigation-stat-label">Investigate</div>
            <div className="investigation-stat-value">{stats.investigate}</div>
            <div className="investigation-stat-copy">Exceptions needing analysis</div>
          </div>

          <div className="investigation-stat-card mismatch">
            <div className="investigation-stat-label">Mismatch cases</div>
            <div className="investigation-stat-value">{stats.mismatch}</div>
            <div className="investigation-stat-copy">Gateway and bank differ</div>
          </div>

          <div className="investigation-stat-card queue">
            <div className="investigation-stat-label">Queue size</div>
            <div className="investigation-stat-value">{rows.length}</div>
            <div className="investigation-stat-copy">Transactions needing attention</div>
          </div>
        </div>

        <div className="investigation-info-card">
          <div className="investigation-info-icon">!</div>
          <div>
            <div className="investigation-info-title">Manual review queue</div>
            <div className="investigation-info-copy">
              These transactions were not given an automatic refund, retry, or wait
              resolution. Inspect the complete lifecycle before taking action.
            </div>
          </div>
        </div>

        <div className="panel investigation-panel">
          <div className="panel-header investigation-panel-header">
            <div>
              <div className="panel-title">Investigation queue</div>
              <div className="panel-subtitle">
                Click a transaction to review the full lifecycle. Use AI assist for a risk assessment.
              </div>
            </div>
            <span className="investigation-hint">Select a transaction →</span>
          </div>

          <div className="table-wrap">
            <table className="ops-table investigation-table">
              <thead>
                <tr>
                  <th>Transaction</th>
                  <th>Payment status</th>
                  <th>Gateway</th>
                  <th>Bank</th>
                  <th>Reconciliation</th>
                  <th>Reason</th>
                  <th>Action</th>
                  <th>AI</th>
                  <th>Created</th>
                </tr>
              </thead>

              <tbody>
                {rows.map(txn => (
                  <tr
                    key={txn.transaction_id}
                    onClick={() => onSelect(txn.transaction_id)}
                    className="investigation-row"
                  >
                    <td>
                      <div className="investigation-txn-cell">
                        <div className="investigation-txn-id mono">
                          {txn.transaction_id}
                        </div>
                        <div className="investigation-txn-amount">
                          {fmtAmount(txn.amount, txn.currency)}
                        </div>
                      </div>
                    </td>

                    <td>
                      <StatusBadge value={txn.status} />
                    </td>

                    <td>
                      <StatusBadge value={txn.gateway?.status} />
                    </td>

                    <td>
                      <StatusBadge value={txn.bank?.status} />
                    </td>

                    <td>
                      <StatusBadge
                        value={txn.reconciliation?.reconciliation_status}
                      />
                    </td>

                    <td className="reason-cell investigation-reason">
                      {txn.reconciliation?.reason || 'Unexpected state'}
                    </td>

                    <td>
                      <StatusBadge
                        value={txn.reconciliation?.action_required || 'MANUAL_REVIEW'}
                      />
                    </td>

                    <td className="ai-action-cell">
                      <button
                        type="button"
                        className="ai-analyze-button"
                        onClick={event => {
                          event.stopPropagation()
                          runAnalysis(txn.transaction_id)
                        }}
                      >
                        <span className="ai-spark">✦</span>
                        Analyze
                      </button>
                    </td>

                    <td className="time-cell">
                      {formatDate(
                        txn.reconciliation?.created_at ||
                        txn.updated_at ||
                        txn.created_at
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {!rows.length && (
            <div className="empty-state compact">
              <div className="empty-title">No investigations are currently waiting</div>
              <div className="empty-copy">
                Transactions requiring manual attention will appear here.
              </div>
            </div>
          )}
        </div>
      </section>

      <AIAnalysisDrawer
        analysis={analysis}
        transaction={analysisTarget}
        loading={analysisLoading}
        error={analysisError}
        onClose={closeAnalysis}
        onOpenTransaction={openTransactionFromAI}
        onAnalyze={runAnalysis}
      />
    </>
  )
}

function OverviewPage({
  summary,
  transactions,
  onNavigate,
  onSelect,
}) {
  const recent = (transactions || []).slice(0, 8)

  return (
    <section className="page-section">
      <StatsCards summary={summary} />

      <AttentionSection
        summary={summary}
        onNavigate={onNavigate}
      />

      <section className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">
              Recent transactions
            </div>

            <div className="panel-subtitle">
              Latest payment activity across the simulated
              lifecycle
            </div>
          </div>

          <button
            type="button"
            className="text-button"
            onClick={() => onNavigate('transactions')}
          >
            View all →
          </button>
        </div>

        <TransactionsTable
          transactions={recent}
          onSelect={onSelect}
        />
      </section>
    </section>
  )
}

const ROUTE_TO_PAGE = {
  '/': 'overview',
  '/transactions': 'transactions',
  '/reconciliation': 'reconciliation',
  '/refunds': 'refunds',
  '/retries': 'retries',
  '/investigations': 'investigations',
  '/event-operations': 'event_operations',
}

const PAGE_TO_ROUTE = Object.fromEntries(
  Object.entries(ROUTE_TO_PAGE).map(([route, page]) => [page, route])
)

function getPageFromPathname(pathname) {
  return ROUTE_TO_PAGE[pathname] || 'overview'
}

export default function App() {
  const [page, setPage] = useState(() =>
    getPageFromPathname(window.location.pathname)
  )
  const [summary, setSummary] = useState(null)
  const [transactions, setTransactions] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [selectedTxn, setSelectedTxn] = useState(null)
  const [spinning, setSpinning] = useState(false)

  // Sidebar open / collapsed state
  const [sidebarCollapsed, setSidebarCollapsed] =
    useState(false)

  const navigateToPage = useCallback(nextPage => {
    const route = PAGE_TO_ROUTE[nextPage] || '/'

    if (window.location.pathname !== route) {
      window.history.pushState({}, '', route)
    }

    setPage(nextPage)
  }, [])

  useEffect(() => {
    const handlePopState = () => {
      const nextPage = getPageFromPathname(window.location.pathname)

      if (nextPage) {
        setPage(nextPage)
      }
    }

    window.addEventListener('popstate', handlePopState)

    return () => {
      window.removeEventListener('popstate', handlePopState)
    }
  }, [])

  const loadData = useCallback(async () => {
    setSpinning(true)
    setLoading(true)
    setError(null)

    try {
      const [summaryData, transactionData] =
        await Promise.all([
          fetchSummary(),
          fetchTransactions(),
        ])

      setSummary(summaryData)
      setTransactions(transactionData)
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        err.message ||
        'Unable to connect to backend.'
      )
    } finally {
      setLoading(false)

      setTimeout(() => {
        setSpinning(false)
      }, 500)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const pageMeta = {
    overview: [
      'Overview',
      'Payment health, exceptions and recent transaction activity',
    ],

    transactions: [
      'Transactions',
      'Search and inspect payment lifecycles',
    ],

    reconciliation: [
      'Reconciliation',
      'Compare gateway and bank outcomes',
    ],

    refunds: [
      'Refunds',
      'Track simulated refund resolution',
    ],

    retries: [
      'Retries',
      'Track retry attempts and outcomes',
    ],

    investigations: [
      'Investigations',
      'Review transactions that need manual attention',
    ],

    event_operations: [
      'Event Operations',
      'Monitor payment events and RabbitMQ delivery',
    ],
  }

  const [title, subtitle] =
    pageMeta[page] || pageMeta.overview

  return (
    <div
      className={`app-shell ${
        sidebarCollapsed
          ? 'sidebar-collapsed'
          : ''
      }`}
    >
      <Sidebar
        activePage={page}
        onNavigate={navigateToPage}
        collapsed={sidebarCollapsed}
        onToggle={() =>
          setSidebarCollapsed(
            previous => !previous
          )
        }
      />

      <main className="main-area">
        <PageHeader
          title={title}
          subtitle={subtitle}
          onRefresh={loadData}
          spinning={spinning}
        />

        <div className="page-content">
          {error && (
            <div className="error-banner">
              <span>
                Unable to connect to backend.
              </span>

              <button
                type="button"
                onClick={loadData}
              >
                Retry
              </button>
            </div>
          )}

          {loading && !summary ? (
            <div className="loading-container full">
              <div className="spinner" />

              <span>
                Loading payment data…
              </span>
            </div>
          ) : (
            <>
              {page === 'overview' && (
                <OverviewPage
                  summary={summary}
                  transactions={transactions}
                  onNavigate={navigateToPage}
                  onSelect={setSelectedTxn}
                />
              )}

              {page === 'transactions' && (
                <TransactionsPage
                  transactions={transactions}
                  onSelect={setSelectedTxn}
                />
              )}

              {page === 'reconciliation' && (
                <ReconciliationPage
                  transactions={transactions}
                  onSelect={setSelectedTxn}
                />
              )}

              {page === 'refunds' && (
                <RefundsPage
                  transactions={transactions}
                  onSelect={setSelectedTxn}
                />
              )}

              {page === 'retries' && (
                <RetriesPage
                  transactions={transactions}
                  onSelect={setSelectedTxn}
                />
              )}

              {page === 'investigations' && (
                <InvestigationsPage
                  transactions={transactions}
                  onSelect={setSelectedTxn}
                />
              )}

              {page === 'event_operations' && (
                <EventOperationsPage />
              )}
            </>
          )}
        </div>
      </main>

      {selectedTxn && (
        <TransactionDetail
          transactionId={selectedTxn}
          onClose={() =>
            setSelectedTxn(null)
          }
        />
      )}
    </div>
  )
}