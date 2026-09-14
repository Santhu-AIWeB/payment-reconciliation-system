import { useMemo, useState } from 'react'
import './App.css'

const API_BASE = 'http://localhost:8002'

const CURRENCIES = [
  { code: 'INR', symbol: '₹' },
  { code: 'USD', symbol: '$' },
  { code: 'EUR', symbol: '€' },
]

function formatAmount(amount, currency = 'INR') {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency,
    maximumFractionDigits: 2,
  }).format(Number(amount || 0))
}

async function postJson(path, payload) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(payload),
  })

  let data = {}

  try {
    data = await response.json()
  } catch {
    data = {}
  }

  if (!response.ok) {
    let message = `Request failed with HTTP ${response.status}.`

    if (typeof data?.detail === 'string') {
      message = data.detail
    } else if (data?.detail) {
      message = JSON.stringify(data.detail)
    } else if (data?.message) {
      message = data.message
    }

    throw new Error(message)
  }

  return data
}

async function getJson(path) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
  })

  let data = {}

  try {
    data = await response.json()
  } catch {
    data = {}
  }

  if (!response.ok) {
    let message = `Request failed with HTTP ${response.status}.`

    if (typeof data?.detail === 'string') {
      message = data.detail
    } else if (data?.detail) {
      message = JSON.stringify(data.detail)
    } else if (data?.message) {
      message = data.message
    }

    throw new Error(message)
  }

  return data
}

function getErrorMessage(error) {
  if (error instanceof TypeError) {
    return 'Unable to reach the payment gateway. Please make sure the Gateway Server is running on port 8002.'
  }

  return error?.message || 'Unable to process the payment.'
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function waitForReconciliation(transactionId) {
  const maxAttempts = 15
  const delayMs = 700

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      const status = await getJson(
        `/api/gateway/transaction/${transactionId}`
      )

      const reconciliation = status.reconciliation

      if (reconciliation) {
        return {
          transaction: {
            transaction_id: transactionId,
          },
          reconciliation,
        }
      }
    } catch (error) {
      console.error(
        `Status check ${attempt} failed:`,
        error
      )
    }

    await sleep(delayMs)
  }

  return null
}

export default function App() {
  const [form, setForm] = useState({
    amount: '',
    currency: 'INR',
  })

  const [paymentMethod, setPaymentMethod] = useState('UPI')
  const [processing, setProcessing] = useState(false)
  const [waitingForReconciliation, setWaitingForReconciliation] =
    useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  const selectedCurrency = useMemo(
    () =>
      CURRENCIES.find(item => item.code === form.currency) ||
      CURRENCIES[0],
    [form.currency]
  )

  function handleChange(event) {
    const { name, value } = event.target

    setForm(previous => ({
      ...previous,
      [name]: value,
    }))
  }

  function resetPayment() {
    setForm({
      amount: '',
      currency: 'INR',
    })

    setPaymentMethod('UPI')
    setProcessing(false)
    setWaitingForReconciliation(false)
    setError('')
    setResult(null)
  }

  async function handlePayment(event) {
    event.preventDefault()

    const amount = Number(form.amount)

    if (!Number.isFinite(amount) || amount <= 0) {
      setError('Enter an amount greater than 0.')
      return
    }

    try {
      setProcessing(true)
      setWaitingForReconciliation(false)
      setError('')
      setResult(null)

      // =================================================
      // STEP 1
      // Send payment ONLY to Gateway Server
      // =================================================

      const paymentResponse = await postJson(
        '/api/gateway/pay',
        {
          amount,
          currency: form.currency,
          account_id: 'DUMMY-1001',
        }
      )

      const transactionId =
        paymentResponse.transaction_id

      // =================================================
      // STEP 2
      // Wait for asynchronous reconciliation
      // =================================================

      setWaitingForReconciliation(true)

      const reconciliationResult =
        await waitForReconciliation(transactionId)

      if (!reconciliationResult?.reconciliation) {
        throw new Error(
          'Payment was created, but the final reconciliation result was not available yet.'
        )
      }

      // =================================================
      // STEP 3
      // Build final customer result
      // =================================================

      const finalReconciliation =
        reconciliationResult.reconciliation

      setResult({
        transaction: {
          transaction_id: transactionId,
          amount: paymentResponse.amount,
          currency: paymentResponse.currency,
        },

        gateway: paymentResponse.gateway,

        bank: paymentResponse.bank,

        bankSync: paymentResponse.bank_sync,

        reconciliation: {
          ...finalReconciliation,
        },

        paymentMethod,
      })
    } catch (err) {
      console.error(err)
      setError(getErrorMessage(err))
    } finally {
      setProcessing(false)
      setWaitingForReconciliation(false)
    }
  }

  // =====================================================
  // RESULT SCREEN
  // =====================================================

  if (result) {
    const reconciliationStatus =
      result.reconciliation?.reconciliation_status ||
      'UNKNOWN'

    const actionRequired =
      result.reconciliation?.action_required ||
      'NONE'

    const isMatched =
      reconciliationStatus === 'MATCHED'

    const isPending =
      reconciliationStatus === 'PENDING'

    return (
      <div className="payment-page">
        <div className="payment-wrapper">
          <div className="payment-brand">
            PayReconcile
          </div>

          <div
            className={`payment-result-card ${
              isMatched ? 'success' : 'exception'
            }`}
          >
            <div className="result-icon">
              {isMatched
                ? '✓'
                : isPending
                  ? '…'
                  : '!'}
            </div>

            <div className="result-eyebrow">
              {isMatched
                ? 'Payment completed'
                : isPending
                  ? 'Payment pending'
                  : 'Payment exception detected'}
            </div>

            <h1>
              {isMatched
                ? 'Payment Successful'
                : isPending
                  ? 'Payment Is Being Confirmed'
                  : 'Payment Requires Reconciliation'}
            </h1>

            <p>
              {isMatched
                ? 'Gateway and bank records are aligned for this payment.'
                : isPending
                  ? 'The payment is waiting for a definitive outcome.'
                  : 'The payment reached an inconsistent state and has been handed to the reconciliation workflow.'}
            </p>

            <div className="result-grid">
              <div>
                <span>Amount</span>

                <strong>
                  {formatAmount(
                    result.transaction?.amount,
                    result.transaction?.currency
                  )}
                </strong>
              </div>

              <div>
                <span>Payment method</span>

                <strong>
                  {result.paymentMethod}
                </strong>
              </div>

              <div>
                <span>Transaction</span>

                <strong className="result-mono">
                  {result.transaction?.transaction_id ||
                    '—'}
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
                <span>Bank Reference</span>

                <strong className="result-mono">
                  {result.bank?.bank_reference || '—'}
                </strong>
              </div>

              <div>
                <span>Reconciliation</span>

                <strong>
                  {reconciliationStatus}
                </strong>
              </div>

              <div>
                <span>Action</span>

                <strong>
                  {actionRequired}
                </strong>
              </div>

              <div>
                <span>Balance After</span>

                <strong>
                  {result.bank?.balance_after !== undefined
                    ? formatAmount(
                        result.bank.balance_after,
                        result.bank.currency || 'INR'
                      )
                    : '—'}
                </strong>
              </div>
            </div>

            {result.reconciliation?.reason && (
              <div className="result-reason">
                <span>System note</span>

                <strong>
                  {result.reconciliation.reason}
                </strong>
              </div>
            )}

            <button
              type="button"
              className="primary-action-button"
              onClick={resetPayment}
            >
              Make another payment
            </button>
          </div>

          <div className="simulation-note">
            Simulation mode · no real money movement
          </div>
        </div>
      </div>
    )
  }

  // =====================================================
  // CUSTOMER PAYMENT SCREEN
  // =====================================================

  return (
    <div className="payment-page">
      <div className="payment-wrapper">
        <div className="payment-brand">
          PayReconcile
        </div>

        <div className="payment-card">
          <div className="payment-eyebrow">
            SECURE PAYMENT
          </div>

          <h1>
            Pay securely
          </h1>

          <p className="payment-subtitle">
            Complete your payment through the PayReconcile checkout.
          </p>

          <form onSubmit={handlePayment}>
            {/* =================================================
                AMOUNT
            ================================================= */}

            <div className="checkout-field">
              <label htmlFor="amount">
                Amount
              </label>

              <div className="amount-input-row">
                <select
                  name="currency"
                  value={form.currency}
                  onChange={handleChange}
                  aria-label="Currency"
                >
                  {CURRENCIES.map(currency => (
                    <option
                      key={currency.code}
                      value={currency.code}
                    >
                      {currency.code}
                    </option>
                  ))}
                </select>

                <input
                  id="amount"
                  name="amount"
                  type="number"
                  value={form.amount}
                  onChange={handleChange}
                  placeholder="500.00"
                  min="0.01"
                  step="0.01"
                  inputMode="decimal"
                  required
                />
              </div>

              {form.amount && (
                <div className="amount-preview">
                  {selectedCurrency.symbol}

                  {Number(
                    form.amount || 0
                  ).toLocaleString('en-IN', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
                </div>
              )}
            </div>

            {/* =================================================
                PAYMENT METHOD
            ================================================= */}

            <div className="checkout-field">
              <label>
                Payment method
              </label>

              <div className="payment-method-grid">
                {[
                  'UPI',
                  'CARD',
                  'NET_BANKING',
                ].map(method => (
                  <button
                    key={method}
                    type="button"
                    className={`method-option ${
                      paymentMethod === method
                        ? 'selected'
                        : ''
                    }`}
                    onClick={() =>
                      setPaymentMethod(method)
                    }
                  >
                    {method === 'NET_BANKING'
                      ? 'Net Banking'
                      : method}
                  </button>
                ))}
              </div>
            </div>

            {/* =================================================
                ERROR
            ================================================= */}

            {error && (
              <div
                className="payment-error"
                role="alert"
              >
                {error}
              </div>
            )}

            {/* =================================================
                PAY BUTTON
            ================================================= */}

            <button
              type="submit"
              className="primary-action-button payment-submit"
              disabled={processing}
            >
              {processing
                ? waitingForReconciliation
                  ? 'Confirming payment…'
                  : 'Processing payment…'
                : `Pay ${
                    form.amount
                      ? formatAmount(
                          form.amount,
                          form.currency
                        )
                      : 'securely'
                  }`}
            </button>
          </form>

          <div className="payment-security-row">
            <span>🔒</span>

            <span>
              Secure simulated checkout
            </span>
          </div>
        </div>

        <div className="simulation-note">
          Simulation mode · no real money movement
        </div>
      </div>
    </div>
  )
}