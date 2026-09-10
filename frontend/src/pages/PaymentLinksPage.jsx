import { useEffect, useState } from 'react'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'

function formatAmount(amount, currency = 'INR') {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency,
    maximumFractionDigits: 2,
  }).format(Number(amount || 0))
}

function formatDate(dateString) {
  if (!dateString) return '—'
  const date = new Date(dateString)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: true,
  })
}

function statusClass(status) {
  if (status === 'ACTIVE') return 'link-status active'
  if (status === 'USED') return 'link-status used'
  if (status === 'EXPIRED') return 'link-status expired'
  if (status === 'CANCELLED') return 'link-status cancelled'
  return 'link-status'
}

export default function PaymentLinksPage() {
  const [links, setLinks] = useState([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const [copiedLinkId, setCopiedLinkId] = useState('')
  const [form, setForm] = useState({ amount: '', currency: 'INR', description: '' })
  const [createdLink, setCreatedLink] = useState(null)

  useEffect(() => { loadLinks() }, [])

  async function loadLinks() {
    try {
      setLoading(true)
      setError('')
      const response = await axios.get(`${API_BASE}/api/payment-links`)
      setLinks(response.data)
    } catch (err) {
      console.error(err)
      setError(err.response?.data?.detail || 'Unable to load payment links.')
    } finally {
      setLoading(false)
    }
  }

  function handleChange(event) {
    const { name, value } = event.target
    setForm(previous => ({ ...previous, [name]: value }))
  }

  async function handleCreate(event) {
    event.preventDefault()
    const amount = Number(form.amount)
    if (!amount || amount <= 0) {
      setError('Enter an amount greater than 0.')
      return
    }
    if (!form.description.trim()) {
      setError('Enter a payment description.')
      return
    }

    try {
      setCreating(true)
      setError('')
      setCreatedLink(null)

      const response = await axios.post(`${API_BASE}/api/payment-links`, {
        amount,
        currency: form.currency.toUpperCase(),
        description: form.description.trim(),
      })

      setCreatedLink(response.data)
      setForm({ amount: '', currency: 'INR', description: '' })
      await loadLinks()
    } catch (err) {
      console.error(err)
      setError(err.response?.data?.detail || 'Unable to create payment link.')
    } finally {
      setCreating(false)
    }
  }

  async function handleCopy(url, linkId) {
    try {
      await navigator.clipboard.writeText(url)
      setCopiedLinkId(linkId)
      setTimeout(() => setCopiedLinkId(''), 1800)
    } catch (err) {
      console.error(err)
      setError('Unable to copy payment URL.')
    }
  }

  return (
    <section className="page-section">
      <div className="section-heading-large payment-links-heading">
        <div>
          <h2>Payment Links</h2>
          <p>Create customer payment links and manage simulated checkout access</p>
        </div>
        <span className="record-count">{links.length} links</span>
      </div>

      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button type="button" onClick={loadLinks}>Retry</button>
        </div>
      )}

      <div className="payment-links-layout">
        <div className="panel create-link-panel">
          <div className="panel-header">
            <div>
              <div className="panel-title">Create payment link</div>
              <div className="panel-subtitle">Generate a safe simulation URL for a customer</div>
            </div>
          </div>

          <form className="payment-link-form" onSubmit={handleCreate}>
            <label>
              <span>Amount</span>
              <input type="number" name="amount" value={form.amount}
                onChange={handleChange} placeholder="500" min="0.01" step="0.01" />
            </label>

            <label>
              <span>Currency</span>
              <select name="currency" value={form.currency} onChange={handleChange}>
                <option value="INR">INR</option>
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
              </select>
            </label>

            <label className="full-width">
              <span>Description</span>
              <input type="text" name="description" value={form.description}
                onChange={handleChange} placeholder="Order #1025" maxLength={200} />
            </label>

            <button type="submit" className="primary-action-button full-width" disabled={creating}>
              {creating ? 'Generating...' : '+ Generate Payment Link'}
            </button>
          </form>

          <div className="simulation-note">Simulation mode · no real money movement</div>
        </div>

        {createdLink && (
          <div className="panel generated-link-panel">
            <div className="generated-success">
              <div className="generated-success-icon">✓</div>
              <div>
                <div className="panel-title">Payment link created</div>
                <div className="panel-subtitle">Share the URL below with the customer</div>
              </div>
            </div>

            <div className="generated-link-id">{createdLink.link_id}</div>

            <div className="generated-url-box">
              <span>{createdLink.payment_url}</span>
              <button type="button"
                onClick={() => handleCopy(createdLink.payment_url, createdLink.link_id)}>
                {copiedLinkId === createdLink.link_id ? 'Copied' : 'Copy'}
              </button>
            </div>

            <div className="generated-link-meta">
              <span>{formatAmount(createdLink.amount, createdLink.currency)}</span>
              <span>Expires {formatDate(createdLink.expires_at)}</span>
            </div>

            <a className="open-payment-link" href={createdLink.payment_url}
              target="_blank" rel="noreferrer">
              Open customer payment page →
            </a>
          </div>
        )}
      </div>

      <div className="panel links-list-panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">Recent payment links</div>
            <div className="panel-subtitle">Customer checkout links created in simulation mode</div>
          </div>
          <button type="button" className="text-button" onClick={loadLinks}>↻ Refresh</button>
        </div>

        {loading ? (
          <div className="loading-container">
            <div className="spinner" />
            <span>Loading payment links...</span>
          </div>
        ) : links.length === 0 ? (
          <div className="empty-state compact">
            <div className="empty-title">No payment links yet</div>
            <div className="empty-copy">Create your first payment link above.</div>
          </div>
        ) : (
          <div className="table-wrap">
            <table className="ops-table">
              <thead>
                <tr>
                  <th>Payment Link</th><th>Amount</th><th>Description</th>
                  <th>Status</th><th>Created</th><th>Expires</th><th />
                </tr>
              </thead>
              <tbody>
                {links.map(link => (
                  <tr key={link.link_id}>
                    <td>
                      <div className="mono">{link.link_id}</div>
                      <div className="payment-link-transaction">{link.transaction_id}</div>
                    </td>
                    <td className="amount-cell">{formatAmount(link.amount, link.currency)}</td>
                    <td className="reason-cell">{link.description}</td>
                    <td><span className={statusClass(link.status)}>{link.status}</span></td>
                    <td className="time-cell">{formatDate(link.created_at)}</td>
                    <td className="time-cell">{formatDate(link.expires_at)}</td>
                    <td>
                      <button type="button" className="copy-link-button"
                        disabled={link.status !== 'ACTIVE'}
                        onClick={() => handleCopy(link.payment_url, link.link_id)}>
                        {copiedLinkId === link.link_id ? 'Copied' : 'Copy URL'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  )
}
