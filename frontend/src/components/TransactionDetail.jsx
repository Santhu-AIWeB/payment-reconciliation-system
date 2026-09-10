import { useEffect, useMemo, useState } from 'react'
import { fetchTransactionDetail, fetchTransactionAudit } from '../api/dashboard'
import StatusBadge from './StatusBadge'

function fmt(dateStr) {
  if (!dateStr) return '—'
  const date = new Date(dateStr)
  if (Number.isNaN(date.getTime())) return '—'

  return date.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  })
}

function fmtAmount(amount, currency) {
  if (amount == null) return '—'

  const symbol = currency === 'INR' ? '₹' : `${currency || ''} `

  return `${symbol}${Number(amount).toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

function copyText(value) {
  if (!value || !navigator.clipboard) return
  navigator.clipboard.writeText(value).catch(() => {})
}

function Icon({ name, size = 18 }) {
  const common = {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': true,
  }

  const paths = {
    back: (
      <>
        <path d="M19 12H5" />
        <path d="m11 18-6-6 6-6" />
      </>
    ),
    copy: (
      <>
        <rect x="9" y="9" width="10" height="10" rx="2" />
        <path d="M15 9V7a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" />
      </>
    ),
    card: (
      <>
        <rect x="3" y="5" width="18" height="14" rx="2" />
        <path d="M3 10h18" />
        <path d="M7 15h3" />
      </>
    ),
    gateway: (
      <>
        <path d="M4 20h16" />
        <path d="M6 17v-7" />
        <path d="M10 17v-7" />
        <path d="M14 17v-7" />
        <path d="M18 17v-7" />
        <path d="m4 8 8-4 8 4" />
      </>
    ),
    bank: (
      <>
        <path d="M3 20h18" />
        <path d="M5 17v-7" />
        <path d="M9 17v-7" />
        <path d="M15 17v-7" />
        <path d="M19 17v-7" />
        <path d="m3 7 9-4 9 4" />
      </>
    ),
    scale: (
      <>
        <path d="M12 4v16" />
        <path d="M5 7h14" />
        <path d="M5 7 2.8 12h4.4L5 7Z" />
        <path d="m19 7-2.2 5h4.4L19 7Z" />
        <path d="M8 20h8" />
      </>
    ),
    timeline: (
      <>
        <circle cx="12" cy="12" r="8" />
        <path d="M12 8v5l3 2" />
      </>
    ),
    refund: (
      <>
        <path d="M9 7H5v4" />
        <path d="M5 11a7 7 0 1 0 2 6" />
        <path d="M5 11 9 7" />
      </>
    ),
    retry: (
      <>
        <path d="M20 7v5h-5" />
        <path d="M19 12a7 7 0 1 0-2 5" />
      </>
    ),
    check: (
      <>
        <circle cx="12" cy="12" r="8" />
        <path d="m8.5 12 2.3 2.3L15.7 9.5" />
      </>
    ),
    alert: (
      <>
        <path d="m12 3 9 17H3L12 3Z" />
        <path d="M12 9v4" />
        <path d="M12 17h.01" />
      </>
    ),
  }

  return <svg {...common}>{paths[name]}</svg>
}

function HeaderStatus({ status }) {
  return (
    <div className="light-status-wrap">
      <StatusBadge value={status} />
    </div>
  )
}

function Metric({ icon, label, value, mono = false }) {
  return (
    <div className="light-metric">
      <div className="light-metric-icon">
        <Icon name={icon} size={17} />
      </div>
      <div className="light-metric-copy">
        <span>{label}</span>
        <strong className={mono ? 'mono' : ''}>{value || '—'}</strong>
      </div>
    </div>
  )
}

function DataField({ label, value, mono = false, full = false, copyable = false, children }) {
  return (
    <div className={`light-data-field ${full ? 'full' : ''}`}>
      <div className="light-data-label">{label}</div>

      <div className={`light-data-value ${mono ? 'mono' : ''}`}>
        {children || <span>{value || '—'}</span>}

        {copyable && value ? (
          <button
            type="button"
            className="light-copy-btn"
            onClick={() => copyText(value)}
            title={`Copy ${label}`}
            aria-label={`Copy ${label}`}
          >
            <Icon name="copy" size={14} />
          </button>
        ) : null}
      </div>
    </div>
  )
}

function Card({ title, subtitle, icon, action, children, className = '' }) {
  return (
    <section className={`light-card ${className}`}>
      <div className="light-card-header">
        <div className="light-card-heading">
          <div className="light-card-icon">
            <Icon name={icon} size={17} />
          </div>

          <div>
            <h3>{title}</h3>
            {subtitle ? <p>{subtitle}</p> : null}
          </div>
        </div>

        {action}
      </div>

      {children}
    </section>
  )
}

function eventTone(eventType = '') {
  if (eventType.includes('TRANSACTION')) return 'blue'
  if (eventType.includes('GATEWAY')) return 'violet'
  if (eventType.includes('BANK')) return 'red'
  if (eventType.includes('RECON')) return 'amber'
  if (eventType.includes('REFUND')) return 'green'
  if (eventType.includes('RETRY')) return 'purple'
  return 'blue'
}

function FlowStep({ title, value, icon, tone = 'neutral' }) {
  return (
    <div className={`light-flow-step ${tone}`}>
      <div className="light-flow-icon">
        <Icon name={icon} size={16} />
      </div>
      <div className="light-flow-text">
        <span>{title}</span>
        <strong>{value || '—'}</strong>
      </div>
    </div>
  )
}

export default function TransactionDetail({ transactionId, onClose }) {
  const [detail, setDetail] = useState(null)
  const [audit, setAudit] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [refundLoading, setRefundLoading] = useState(false)
  const [refundError, setRefundError] = useState(null)
  const [refundMessage, setRefundMessage] = useState(null)
  const [retryLoading, setRetryLoading] = useState(false)
  const [retryError, setRetryError] = useState(null)
  const [retryMessage, setRetryMessage] = useState(null)

  useEffect(() => {
    let active = true

    setLoading(true)
    setError(null)
    setDetail(null)
    setAudit([])

    fetchTransactionDetail(transactionId)
      .then(transactionDetail => {
        if (!active) return

        setDetail(transactionDetail)

        return fetchTransactionAudit(transactionId)
          .then(auditEvents => {
            if (active) {
              setAudit(Array.isArray(auditEvents) ? auditEvents : [])
            }
          })
          .catch(auditError => {
            console.warn('Audit timeline unavailable:', auditError)
            if (active) setAudit([])
          })
      })
      .catch(err => {
        if (!active) return

        setError(
          err.response?.data?.detail ||
          err.message ||
          'Unable to load transaction.'
        )
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [transactionId])

  const txn = detail?.transaction || {}
  const gateway = detail?.gateway
  const bank = detail?.bank
  const rec = detail?.reconciliation
  const refund = detail?.refund
  const retries = detail?.retries || []

  const exception = Boolean(
    rec &&
    rec.reconciliation_status &&
    rec.reconciliation_status !== 'MATCHED'
  )

  const exceptionInfo = useMemo(() => {
    if (!exception) {
      return {
        title: 'Payment reconciled',
        message: 'Gateway and bank records are aligned.',
        tone: 'success',
      }
    }

    const actionMap = {
      REFUND: {
        title: 'Refund required',
        tone: 'blue',
      },
      RETRY: {
        title: 'Retry required',
        tone: 'purple',
      },
      INVESTIGATE: {
        title: 'Investigation required',
        tone: 'orange',
      },
      WAIT: {
        title: 'Waiting for confirmation',
        tone: 'teal',
      },
      BLOCK: {
        title: 'Processing blocked',
        tone: 'red',
      },
    }

    const selected = actionMap[rec?.action_required] || {
      title: 'Reconciliation exception',
      tone: 'amber',
    }

    return {
      ...selected,
      message:
        rec?.reason ||
        'The gateway and bank records require further review.',
    }
  }, [exception, rec])

  const processRefund = async () => {
    if (
      !transactionId ||
      refundLoading ||
      refund ||
      rec?.action_required !== 'REFUND'
    ) {
      return
    }

    setRefundLoading(true)
    setRefundError(null)
    setRefundMessage(null)

    try {
      const response = await fetch('http://localhost:8000/api/refunds/process', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          transaction_id: transactionId,
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data?.detail || 'Refund processing failed.')
      }

      setRefundMessage(
        `Refund ${String(data.status || 'processed').toLowerCase()} successfully.`
      )

      const [updatedDetail, updatedAudit] = await Promise.all([
        fetchTransactionDetail(transactionId),
        fetchTransactionAudit(transactionId),
      ])

      setDetail(updatedDetail)
      setAudit(Array.isArray(updatedAudit) ? updatedAudit : [])
    } catch (err) {
      setRefundError(
        err?.message || 'Unable to process the simulated refund.'
      )
    } finally {
      setRefundLoading(false)
    }
  }

  const processRetry = async () => {
    if (
      !transactionId ||
      retryLoading ||
      rec?.action_required !== 'RETRY'
    ) {
      return
    }

    setRetryLoading(true)
    setRetryError(null)
    setRetryMessage(null)

    try {
      const response = await fetch('http://localhost:8000/api/retry/process', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          transaction_id: transactionId,
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data?.detail || 'Retry processing failed.')
      }

      setRetryMessage(
        `Retry attempt ${data.attempt_number || ''} ${String(data.status || 'processed').toLowerCase()}.`
      )

      const [updatedDetail, updatedAudit] = await Promise.all([
        fetchTransactionDetail(transactionId),
        fetchTransactionAudit(transactionId),
      ])

      setDetail(updatedDetail)
      setAudit(Array.isArray(updatedAudit) ? updatedAudit : [])
    } catch (err) {
      setRetryError(
        err?.message || 'Unable to process the simulated retry.'
      )
    } finally {
      setRetryLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="detail-overlay light-detail-overlay">
        <div className="light-detail-panel">
          <div className="light-loading">
            <div className="light-loader" />
            <div>
              <strong>Loading transaction</strong>
              <span>{transactionId}</span>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div
        className="detail-overlay light-detail-overlay"
        onClick={e => e.target === e.currentTarget && onClose()}
      >
        <div className="light-detail-panel">
          <div className="light-error">
            <div className="light-error-icon">
              <Icon name="alert" size={20} />
            </div>
            <h3>Unable to load transaction</h3>
            <p>{error}</p>
            <button type="button" className="light-secondary-btn" onClick={onClose}>
              Close
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div
      className="detail-overlay light-detail-overlay"
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div className="light-detail-panel">
        <header className="light-page-header">
          <div>
            <button type="button" className="light-back-link" onClick={onClose}>
              <Icon name="back" size={16} />
              Back to Transactions
            </button>

            <div className="light-title-row">
              <div>
                <div className="light-eyebrow">Payment transaction</div>

                <div className="light-heading-line">
                  <h1>Transaction Details</h1>
                  <button
                    type="button"
                    className="light-title-copy"
                    onClick={() => copyText(transactionId)}
                    title="Copy transaction ID"
                    aria-label="Copy transaction ID"
                  >
                    <Icon name="copy" size={15} />
                  </button>
                  <span className="light-title-id mono">{transactionId}</span>
                </div>

                <p className="light-page-subtitle">
                  Complete information and payment lifecycle for this transaction
                </p>
              </div>

              <div className="light-heading-actions">
                <HeaderStatus status={txn.status} />

                <button
                  type="button"
                  className="light-close-btn"
                  onClick={onClose}
                  aria-label="Close transaction details"
                >
                  ×
                </button>
              </div>
            </div>
          </div>
        </header>

        <main className="light-content">
          <section className="light-summary">
            <Metric icon="card" label="Amount" value={fmtAmount(txn.amount, txn.currency)} />
            <Metric icon="card" label="Currency" value={txn.currency} />
            <Metric icon="timeline" label="Created At" value={fmt(txn.created_at)} />
            <Metric icon="copy" label="Transaction ID" value={transactionId} mono />
          </section>

          <section className={`light-exception light-exception-${exceptionInfo.tone}`}>
            <div className="light-exception-icon">
              <Icon
                name={exceptionInfo.tone === 'success' ? 'check' : 'alert'}
                size={18}
              />
            </div>

            <div className="light-exception-copy">
              <strong>{exceptionInfo.title}</strong>
              <p>{exceptionInfo.message}</p>
            </div>

            {exception && rec?.action_required ? (
              <StatusBadge value={rec.action_required} />
            ) : null}
          </section>

          <Card
            title="Payment Lifecycle"
            subtitle="Current state across transaction, gateway, bank and reconciliation"
            icon="timeline"
            className="light-lifecycle-card"
          >
            <div className="light-flow">
              <FlowStep
                title="Transaction"
                value={txn.status}
                icon="card"
                tone="blue"
              />
              <div className="light-flow-line" />

              <FlowStep
                title="Gateway"
                value={gateway?.status}
                icon="gateway"
                tone="violet"
              />
              <div className="light-flow-line" />

              <FlowStep
                title="Bank"
                value={bank?.status}
                icon="bank"
                tone={bank?.status === 'NOT_DEBITED' ? 'red' : 'teal'}
              />
              <div className="light-flow-line" />

              <FlowStep
                title="Reconciliation"
                value={rec?.reconciliation_status}
                icon="scale"
                tone={rec?.reconciliation_status === 'MISMATCH' ? 'amber' : 'green'}
              />
            </div>
          </Card>

          <div className="light-layout">
            <div className="light-main-column">
              <Card title="Payment Gateway" subtitle="Gateway processing result" icon="gateway">
                {gateway ? (
                  <div className="light-data-grid">
                    <DataField
                      label="Status"
                      value={gateway.status}
                    />
                    <DataField
                      label="Processed At"
                      value={fmt(gateway.created_at)}
                    />
                    <DataField
                      label="Reference"
                      value={gateway.gateway_reference}
                      mono
                      copyable
                    />
                    <DataField
                      label="Message"
                      value={gateway.response_message}
                      full
                    />
                  </div>
                ) : (
                  <div className="light-empty">No gateway record yet.</div>
                )}
              </Card>

              <Card title="Bank Simulator" subtitle="Simulated bank outcome" icon="bank">
                {bank ? (
                  <div className="light-data-grid">
                    <DataField label="Status" value={bank.status} />
                    <DataField label="Processed At" value={fmt(bank.created_at)} />
                    <DataField
                      label="Reference"
                      value={bank.bank_reference}
                      mono
                      copyable
                    />
                    <DataField
                      label="Message"
                      value={bank.response_message}
                      full
                    />
                  </div>
                ) : (
                  <div className="light-empty">No bank record yet.</div>
                )}
              </Card>

              <Card
                title="Reconciliation"
                subtitle="Gateway versus bank outcome"
                icon="scale"
              >
                {rec ? (
                  <div className="light-data-grid">
                    <DataField label="Status">
                      <StatusBadge value={rec.reconciliation_status} />
                    </DataField>

                    <DataField label="Action Required">
                      <StatusBadge value={rec.action_required} />
                    </DataField>

                    <DataField
                      label="Reconciled At"
                      value={fmt(rec.created_at)}
                    />

                    <DataField
                      label="Resolved At"
                      value={fmt(rec.resolved_at)}
                    />

                    <DataField
                      label="Reason"
                      value={rec.reason}
                      full
                    />
                  </div>
                ) : (
                  <div className="light-empty">Not reconciled yet.</div>
                )}
              </Card>
            </div>

            <aside className="light-side-column">
              <Card
                title="Audit Timeline"
                subtitle={`${audit.length} recorded lifecycle event${audit.length === 1 ? '' : 's'}`}
                icon="timeline"
                className="light-audit-card"
              >
                {audit.length ? (
                  <div className="light-timeline">
                    {audit.map((event, index) => {
                      const tone = eventTone(event.event_type)

                      return (
                        <div
                          className="light-timeline-event"
                          key={`${event.event_type}-${event.timestamp}-${index}`}
                        >
                          <div className={`light-timeline-marker ${tone}`}>
                            {index === audit.length - 1 ? (
                              <span className="light-marker-dot" />
                            ) : null}
                          </div>

                          <div className="light-timeline-content">
                            <div className="light-timeline-head">
                              <strong>{event.title}</strong>
                              <time>{fmt(event.timestamp)}</time>
                            </div>

                            <p>{event.description}</p>

                            {event.reference ? (
                              <span className="light-reference mono">
                                {event.reference}
                              </span>
                            ) : null}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <div className="light-empty">No audit events recorded yet.</div>
                )}
              </Card>

              <Card
                title="Refund"
                subtitle="Refund workflow status"
                icon="refund"
                action={
                  <span className={`light-mini-state ${refund ? 'present' : 'muted'}`}>
                    {refund ? 'Initiated' : 'Not initiated'}
                  </span>
                }
              >
                {refund ? (
                  <>
                    <div
                      className="light-data-grid"
                      style={{
                        marginBottom: 0,
                      }}
                    >
                      <DataField label="Status">
                        <StatusBadge value={refund.status} />
                      </DataField>

                      <DataField
                        label="Amount"
                        value={fmtAmount(refund.amount, txn.currency)}
                      />

                      <DataField
                        label="Reference"
                        value={refund.refund_reference}
                        mono
                        copyable
                        full
                      />

                      <DataField
                        label="Completed At"
                        value={fmt(refund.completed_at)}
                        full
                      />
                    </div>

                    <div
                      style={{
                        margin: '14px 14px 14px',
                        padding: '12px 14px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 12,
                        border: '1px solid #b7ebd0',
                        borderRadius: 10,
                        background: '#effbf4',
                      }}
                    >
                      <div
                        style={{
                          width: 32,
                          height: 32,
                          flex: '0 0 32px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          borderRadius: '50%',
                          background: '#d9f7e7',
                          color: '#12b76a',
                          fontSize: 18,
                          fontWeight: 900,
                        }}
                      >
                        ✓
                      </div>

                      <div
                        style={{
                          minWidth: 0,
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 3,
                        }}
                      >
                        <strong
                          style={{
                            color: '#087443',
                            fontSize: 12,
                            fontWeight: 800,
                            lineHeight: 1.25,
                          }}
                        >
                          Refund completed successfully.
                        </strong>

                        <span
                          style={{
                            color: '#667085',
                            fontSize: 10,
                            lineHeight: 1.4,
                          }}
                        >
                          The simulated refund has been processed and recorded.
                        </span>
                      </div>
                    </div>
                  </>
                ) : (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 16,
                      padding: '12px 14px',
                      borderTop: '1px solid #eef1f5',
                      background: '#fbfcfe',
                    }}
                  >
                    <div
                      style={{
                        minWidth: 0,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 4,
                      }}
                    >
                      <strong
                        style={{
                          color: '#344054',
                          fontSize: 10,
                          fontWeight: 800,
                          lineHeight: 1.2,
                        }}
                      >
                        No refund initiated
                      </strong>
                      <span
                        style={{
                          color: '#8490a3',
                          fontSize: 9,
                          lineHeight: 1.45,
                        }}
                      >
                        {rec?.action_required === 'REFUND'
                          ? 'This transaction is eligible for a simulated refund.'
                          : 'No refund workflow has been started for this transaction.'}
                      </span>
                    </div>

                    {rec?.action_required === 'REFUND' ? (
                      <button
                      type="button"
                      onClick={processRefund}
                      disabled={refundLoading}
                      aria-label="Process simulated refund"
                      style={{
                        flexShrink: 0,
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: 7,
                        minHeight: 34,
                        padding: '0 13px',
                        border: '1px solid #d0d5dd',
                        borderRadius: 8,
                        background: '#ffffff',
                        color: '#175cd3',
                        boxShadow: '0 1px 2px rgba(16, 24, 40, 0.05)',
                        cursor: refundLoading ? 'not-allowed' : 'pointer',
                        fontFamily: 'inherit',
                        fontSize: 10,
                        fontWeight: 800,
                        lineHeight: 1,
                        opacity: refundLoading ? 0.55 : 1,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      <Icon name="refund" size={13} />
                      <span>
                        {refundLoading ? 'Processing…' : 'Process refund'}
                      </span>
                    </button>
                    ) : null}
                  </div>
                )}

                {refundMessage ? (
                  <div className="light-action-message success">
                    {refundMessage}
                  </div>
                ) : null}

                {refundError ? (
                  <div className="light-action-message error">
                    {refundError}
                  </div>
                ) : null}
              </Card>

              <Card
                title="Retry"
                subtitle="Retry workflow status"
                icon="retry"
                action={
                  retries.length ? (
                    <span className="light-mini-state present">
                      {retries.length} attempt{retries.length === 1 ? '' : 's'}
                    </span>
                  ) : (
                    <span className="light-mini-state muted">
                      Not initiated
                    </span>
                  )
                }
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 16,
                    padding: '12px 14px',
                    borderTop: '1px solid #eef1f5',
                    background: '#fbfcfe',
                  }}
                >
                  <div
                    style={{
                      minWidth: 0,
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 4,
                    }}
                  >
                    <strong
                      style={{
                        color: '#344054',
                        fontSize: 10,
                        fontWeight: 800,
                        lineHeight: 1.2,
                      }}
                    >
                      {retries.length
                        ? `Retry attempt${retries.length === 1 ? '' : 's'} recorded`
                        : 'No retry attempts'}
                    </strong>

                    <span
                      style={{
                        color: '#8490a3',
                        fontSize: 9,
                        lineHeight: 1.45,
                      }}
                    >
                      {rec?.action_required === 'RETRY'
                        ? 'This transaction is eligible for a simulated retry.'
                        : 'No retry workflow is currently required.'}
                    </span>
                  </div>

                  {rec?.action_required === 'RETRY' ? (
                    <button
                      type="button"
                      onClick={processRetry}
                      disabled={retryLoading}
                      aria-label="Process simulated retry"
                      style={{
                        flexShrink: 0,
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: 7,
                        minHeight: 34,
                        padding: '0 13px',
                        border: '1px solid #6941c6',
                        borderRadius: 8,
                        background: '#ffffff',
                        color: '#6941c6',
                        boxShadow: '0 1px 2px rgba(16, 24, 40, 0.05)',
                        cursor: retryLoading ? 'not-allowed' : 'pointer',
                        fontFamily: 'inherit',
                        fontSize: 10,
                        fontWeight: 800,
                        lineHeight: 1,
                        opacity: retryLoading ? 0.55 : 1,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      <Icon name="retry" size={13} />
                      <span>
                        {retryLoading ? 'Processing…' : 'Process retry'}
                      </span>
                    </button>
                  ) : null}
                </div>

                {retryMessage ? (
                  <div
                    style={{
                      margin: '0 14px 12px',
                      padding: '9px 10px',
                      border: '1px solid #d9d6fe',
                      borderRadius: 8,
                      background: '#f7f5ff',
                      color: '#6941c6',
                      fontSize: 9,
                      lineHeight: 1.4,
                    }}
                  >
                    {retryMessage}
                  </div>
                ) : null}

                {retryError ? (
                  <div
                    style={{
                      margin: '0 14px 12px',
                      padding: '9px 10px',
                      border: '1px solid #f3c5c5',
                      borderRadius: 8,
                      background: '#fff3f3',
                      color: '#b42318',
                      fontSize: 9,
                      lineHeight: 1.4,
                    }}
                  >
                    {retryError}
                  </div>
                ) : null}
              </Card>

              <Card
                title={`Retry Attempts (${retries.length})`}
                subtitle="Recovery attempts recorded for this payment"
                icon="retry"
              >
                {retries.length ? (
                  <div className="light-retry-table-wrap">
                    <table className="light-retry-table">
                      <thead>
                        <tr>
                          <th>#</th>
                          <th>Status</th>
                          <th>Reference</th>
                          <th>Attempted At</th>
                        </tr>
                      </thead>

                      <tbody>
                        {retries.map(retry => (
                          <tr key={retry.retry_reference}>
                            <td>
                              <span className="light-attempt-number">
                                {retry.attempt_number}
                              </span>
                            </td>

                            <td>
                              <StatusBadge value={retry.status} />
                            </td>

                            <td className="mono light-retry-reference">
                              {retry.retry_reference}
                            </td>

                            <td>{fmt(retry.created_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="light-empty">No retry attempts.</div>
                )}
              </Card>
            </aside>
          </div>
        </main>
      </div>
    </div>
  )
}
