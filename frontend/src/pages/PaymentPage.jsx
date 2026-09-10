import { useEffect, useState } from 'react'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'

const outcomeOptions = [
  {
    value: 'SUCCESS',
    label: 'Successful Payment',
    description:
      'Gateway succeeds and the bank records a debit.',
  },
  {
    value: 'FAILED',
    label: 'Failed Payment',
    description:
      'Gateway fails while the bank still records a debit.',
  },
  {
    value: 'TIMEOUT',
    label: 'Payment Timeout',
    description:
      'Gateway times out while the bank records a debit.',
  },
]

function formatAmount(amount, currency = 'INR') {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency,
    maximumFractionDigits: 2,
  }).format(Number(amount || 0))
}

function formatDateTime(dateString) {
  if (!dateString) return '—'

  const date = new Date(dateString)

  if (Number.isNaN(date.getTime())) {
    return '—'
  }

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

function getResultInfo(result) {
  const reconciliationStatus =
    result.reconciliation?.status

  const action =
    result.reconciliation?.action_required

  const gatewayStatus =
    result.gateway?.status

  const bankStatus =
    result.bank?.status

  // SUCCESS / MATCHED
  if (
    reconciliationStatus === 'MATCHED' &&
    gatewayStatus === 'SUCCESS' &&
    bankStatus === 'DEBITED'
  ) {
    return {
      type: 'success',
      icon: '✓',
      eyebrow: 'Payment completed',
      title: 'Payment Successful',
      message:
        'Your payment was completed successfully and the gateway and bank records match.',
      notice: null,
    }
  }

  // FAILED + DEBITED
  if (action === 'REFUND') {
    return {
      type: 'exception',
      icon: '!',
      eyebrow: 'Payment exception detected',
      title: 'Payment Under Review',
      message:
        'The payment gateway reported a failure, but the bank simulator shows a debit.',
      notice:
        'Please do not make another payment for this order. The transaction has been flagged for refund handling.',
    }
  }

  // TIMEOUT + DEBITED
  if (action === 'INVESTIGATE') {
    return {
      type: 'exception',
      icon: '!',
      eyebrow: 'Payment verification required',
      title: 'Payment Verification in Progress',
      message:
        'The payment response timed out, but the bank simulator shows a debit.',
      notice:
        'Please do not make another payment. The transaction has been flagged for investigation so the final payment state can be verified.',
    }
  }

  // Generic fallback
  return {
    type: 'exception',
    icon: '!',
    eyebrow: 'Payment exception detected',
    title: 'Payment Requires Review',
    message:
      'The payment reached an unexpected state and has been sent to the reconciliation system.',
    notice:
      'Please do not make another payment until the transaction status has been verified.',
  }
}

export default function PaymentPage() {
  const linkId =
    window.location.pathname
      .split('/pay/')[1]
      ?.split('/')[0]

  const [paymentLink, setPaymentLink] = useState(null)
  const [selectedOutcome, setSelectedOutcome] =
    useState('SUCCESS')
  const [loading, setLoading] = useState(true)
  const [paying, setPaying] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  useEffect(() => {
    if (!linkId) {
      setError('Invalid payment link.')
      setLoading(false)
      return
    }

    loadPaymentLink()
  }, [linkId])

  async function loadPaymentLink() {
    try {
      setLoading(true)
      setError('')

      const response = await axios.get(
        `${API_BASE}/api/payment-links/${linkId}`
      )

      setPaymentLink(response.data)
    } catch (err) {
      console.error(err)

      setError(
        err.response?.data?.detail ||
          'Unable to load this payment link.'
      )
    } finally {
      setLoading(false)
    }
  }

  async function handlePayment() {
    if (
      !paymentLink ||
      paymentLink.status !== 'ACTIVE'
    ) {
      return
    }

    try {
      setPaying(true)
      setError('')
      setResult(null)

      const response = await axios.post(
        `${API_BASE}/api/payment-links/${linkId}/pay`,
        {
          outcome: selectedOutcome,
        }
      )

      setResult(response.data)

      setPaymentLink(previous => ({
        ...previous,
        status: 'USED',
      }))
    } catch (err) {
      console.error(err)

      setError(
        err.response?.data?.detail ||
          'Unable to process the simulated payment.'
      )
    } finally {
      setPaying(false)
    }
  }

  if (loading) {
    return (
      <div className="payment-page">
        <div className="payment-loading">
          Loading payment details...
        </div>
      </div>
    )
  }

  if (error && !paymentLink) {
    return (
      <div className="payment-page">
        <div className="payment-card error-card">
          <div className="payment-brand">
            PayReconcile
          </div>

          <h1>Payment Link Unavailable</h1>

          <p>{error}</p>

          <button
            type="button"
            className="secondary-button"
            onClick={() => {
              window.location.href = '/'
            }}
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    )
  }

  if (!paymentLink) {
    return null
  }

  /*
   * ==============================
   * CUSTOMER RESULT SCREEN
   * ==============================
   */
  if (result) {
    const resultInfo = getResultInfo(result)

    return (
      <div className="payment-page">
        <div className="payment-wrapper">
          <div className="payment-brand">
            PayReconcile
          </div>

          <div
            className={`payment-result-card ${resultInfo.type}`}
          >
            <div className="result-icon">
              {resultInfo.icon}
            </div>

            <div className="result-eyebrow">
              {resultInfo.eyebrow}
            </div>

            <h1>{resultInfo.title}</h1>

            <p>
              {resultInfo.message}
            </p>

            <div className="result-grid">
              <div>
                <span>Amount</span>
                <strong>
                  {formatAmount(
                    result.amount,
                    result.currency
                  )}
                </strong>
              </div>

              <div>
                <span>Transaction</span>
                <strong className="result-mono">
                  {result.transaction_id}
                </strong>
              </div>

              <div>
                <span>Gateway</span>
                <strong>
                  {result.gateway?.status || '—'}
                </strong>
              </div>

              <div>
                <span>Bank</span>
                <strong>
                  {result.bank?.status || '—'}
                </strong>
              </div>

              <div>
                <span>Reconciliation</span>
                <strong>
                  {result.reconciliation?.status || '—'}
                </strong>
              </div>

              <div>
                <span>System Action</span>
                <strong>
                  {result.reconciliation
                    ?.action_required || '—'}
                </strong>
              </div>

              <div>
                <span>Processed At</span>
                <strong>
                  {formatDateTime(
                    result.processed_at
                  )}
                </strong>
              </div>
            </div>

            {result.reconciliation?.reason && (
              <div className="result-reason">
                <span>System decision</span>

                <strong>
                  {result.reconciliation.reason}
                </strong>
              </div>
            )}

            {resultInfo.notice && (
              <div className="customer-notice">
                {resultInfo.notice}
              </div>
            )}

            <div className="simulation-result-note">
              Simulation only · No real money movement
            </div>

            <button
              type="button"
              className="back-dashboard"
              onClick={() => {
                window.location.href = '/'
              }}
            >
              ← Return to dashboard
            </button>
          </div>
        </div>
      </div>
    )
  }

  /*
   * ==============================
   * CUSTOMER PAYMENT SCREEN
   * ==============================
   */
  return (
    <div className="payment-page">
      <div className="payment-wrapper">
        <div className="payment-brand">
          PayReconcile
        </div>

        <div className="simulation-banner">
          <div className="simulation-icon">
            !
          </div>

          <div>
            <strong>Simulation Mode</strong>

            <p>
              This is a payment-system simulation.
              No real money will be transferred.
            </p>
          </div>
        </div>

        <div className="payment-card">
          <div className="merchant-section">
            <span className="payment-label">
              Payment Request
            </span>

            <h1>
              Pay{' '}
              {formatAmount(
                paymentLink.amount,
                paymentLink.currency
              )}
            </h1>

            <p className="payment-description">
              {paymentLink.description}
            </p>
          </div>

          <div className="payment-divider" />

          <div className="payment-info-row">
            <span>Payment Link</span>

            <strong>
              {paymentLink.link_id}
            </strong>
          </div>

          <div className="payment-info-row">
            <span>Currency</span>

            <strong>
              {paymentLink.currency}
            </strong>
          </div>

          <div className="payment-info-row">
            <span>Status</span>

            <strong className="active-status">
              {paymentLink.status}
            </strong>
          </div>

          <div className="payment-method-section">
            <span className="payment-label">
              Payment Method
            </span>

            <div className="payment-method-card selected">
              <div className="method-icon">
                ₹
              </div>

              <div>
                <strong>
                  Simulated Payment
                </strong>

                <span>
                  No real payment credentials required
                </span>
              </div>

              <div className="method-check">
                ✓
              </div>
            </div>
          </div>

          <div className="outcome-section">
            <div className="section-heading">
              <span className="payment-label">
                Simulation Outcome
              </span>

              <span className="developer-note">
                Testing control
              </span>
            </div>

            <div className="outcome-options">
              {outcomeOptions.map(option => (
                <button
                  key={option.value}
                  type="button"
                  className={`outcome-option ${
                    selectedOutcome === option.value
                      ? 'selected'
                      : ''
                  }`}
                  onClick={() =>
                    setSelectedOutcome(
                      option.value
                    )
                  }
                >
                  <div className="outcome-radio">
                    {selectedOutcome ===
                    option.value
                      ? '●'
                      : ''}
                  </div>

                  <div className="outcome-content">
                    <strong>
                      {option.label}
                    </strong>

                    <span>
                      {option.description}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div className="payment-error">
              {error}
            </div>
          )}

          <button
            type="button"
            className="pay-button"
            onClick={handlePayment}
            disabled={
              paying ||
              paymentLink.status !== 'ACTIVE'
            }
          >
            {paying
              ? 'Processing Simulation...'
              : `Pay ${formatAmount(
                  paymentLink.amount,
                  paymentLink.currency
                )}`}
          </button>

          <p className="secure-note">
            Simulation only · No real money movement
          </p>
        </div>

        <button
          type="button"
          className="back-dashboard"
          onClick={() => {
            window.location.href = '/'
          }}
        >
          ← Back to dashboard
        </button>
      </div>
    </div>
  )
}