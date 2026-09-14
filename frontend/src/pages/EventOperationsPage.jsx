import { useEffect, useMemo, useState } from 'react'
import { fetchEvents } from '../api/events'

function formatDate(dateStr) {
  if (!dateStr) return '—'

  const date = new Date(dateStr)

  if (Number.isNaN(date.getTime())) {
    return dateStr
  }

  return date.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  })
}

function formatEventType(eventType) {
  if (!eventType) return 'Unknown'

  return eventType
    .replaceAll('_', ' ')
    .toLowerCase()
    .replace(/\b\w/g, letter => letter.toUpperCase())
}

function getStatusLabel(status) {
  return status || 'UNKNOWN'
}

function getBrokerStatus(event) {
  if (event.broker_error) {
    return 'ERROR'
  }

  if (event.broker_published_at) {
    return 'PUBLISHED'
  }

  return 'NOT PUBLISHED'
}

function getBrokerTone(event) {
  if (event.broker_error) {
    return 'danger'
  }

  if (event.broker_published_at) {
    return 'success'
  }

  return 'neutral'
}

export default function EventOperationsPage() {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [selectedEvent, setSelectedEvent] = useState(null)

  const loadEvents = async () => {
    setLoading(true)
    setError(null)

    try {
      const data = await fetchEvents()
      setEvents(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(
        err?.message ||
          'Unable to connect to the payment events endpoint.'
      )
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadEvents()
  }, [])

  const filteredEvents = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase()

    return events.filter(event => {
      if (
        statusFilter !== 'ALL' &&
        event.status !== statusFilter
      ) {
        return false
      }

      if (!normalizedSearch) {
        return true
      }

      return [
        event.event_id,
        event.event_type,
        event.transaction_id,
        event.correlation_id,
        event.status,
      ]
        .filter(Boolean)
        .some(value =>
          String(value)
            .toLowerCase()
            .includes(normalizedSearch)
        )
    })
  }, [events, search, statusFilter])

  const stats = useMemo(
    () => ({
      total: events.length,
      completed: events.filter(
        event => event.status === 'COMPLETED'
      ).length,
      pending: events.filter(
        event => event.status === 'PENDING'
      ).length,
      failed: events.filter(
        event => event.status === 'FAILED'
      ).length,
      processing: events.filter(
        event => event.status === 'PROCESSING'
      ).length,
      published: events.filter(
        event => Boolean(event.broker_published_at)
      ).length,
    }),
    [events]
  )

  const clearFilters = () => {
    setSearch('')
    setStatusFilter('ALL')
  }

  return (
    <section className="page-section event-operations-page">
      {/* Section heading */}
      <div className="section-heading-large">
        <div>
          <h2>Payment events</h2>
          <p>
            Monitor event processing and RabbitMQ delivery
          </p>
        </div>

        <span className="record-count">
          {filteredEvents.length} records
        </span>
      </div>

      {/* Event statistics */}
      <div className="recon-stat-grid event-stat-grid">
        <div className="recon-stat-card total">
          <div className="recon-stat-label">
            Recent events
          </div>

          <div className="recon-stat-value">
            {stats.total}
          </div>

          <div className="recon-stat-copy">
            Latest payment lifecycle events displayed below
          </div>
        </div>

        <div className="recon-stat-card matched">
          <div className="recon-stat-label">
            Completed
          </div>

          <div className="recon-stat-value">
            {stats.completed}
          </div>

          <div className="recon-stat-copy">
            Successfully processed
          </div>
        </div>

        <div className="recon-stat-card pending">
          <div className="recon-stat-label">
            Pending
          </div>

          <div className="recon-stat-value">
            {stats.pending}
          </div>

          <div className="recon-stat-copy">
            Waiting for processing
          </div>
        </div>

        <div className="recon-stat-card mismatch">
          <div className="recon-stat-label">
            Failed
          </div>

          <div className="recon-stat-value">
            {stats.failed}
          </div>

          <div className="recon-stat-copy">
            Events needing attention
          </div>
        </div>
      </div>

      {/* RabbitMQ status */}
      <div className="event-operations-info">
        <div className="event-operations-info-main">
          <div className="event-operations-info-icon">
            ↔
          </div>

          <div>
            <div className="event-operations-info-title">
              Event delivery
            </div>

            <div className="event-operations-info-copy">
              {stats.published} of {stats.total} displayed events have been
              published to RabbitMQ. {stats.processing} displayed events are
              currently processing.
            </div>
          </div>
        </div>

        <button
          type="button"
          className="text-button"
          onClick={loadEvents}
          disabled={loading}
        >
          {loading ? 'Refreshing…' : 'Refresh events'}
        </button>
      </div>

      {error && (
        <div className="error-banner">
          <span>{error}</span>

          <button type="button" onClick={loadEvents}>
            Retry
          </button>
        </div>
      )}

      {/* Filters */}
      <div className="toolbar event-toolbar">
        <div className="search-wrap">
          <span className="search-icon">⌕</span>

          <input
            type="text"
            value={search}
            onChange={event =>
              setSearch(event.target.value)
            }
            placeholder="Search event ID or transaction ID..."
            aria-label="Search payment events"
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
          value={statusFilter}
          onChange={event =>
            setStatusFilter(event.target.value)
          }
          aria-label="Filter payment events"
        >
          <option value="ALL">All statuses</option>
          <option value="COMPLETED">Completed</option>
          <option value="PENDING">Pending</option>
          <option value="PROCESSING">Processing</option>
          <option value="FAILED">Failed</option>
        </select>

        {(search || statusFilter !== 'ALL') && (
          <button
            type="button"
            className="text-button"
            onClick={clearFilters}
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Events table */}
      <div className="panel event-panel">
        <div className="panel-header event-panel-header">
          <div>
            <div className="panel-title">
              Event operations
            </div>

            <div className="panel-subtitle">
              Inspect event status, delivery state and payload
            </div>
          </div>

          <span className="event-panel-hint">
            {loading
              ? 'Loading…'
              : `${filteredEvents.length} shown`}
          </span>
        </div>

        <div className="table-wrap">
          <table className="ops-table event-table">
            <thead>
              <tr>
                <th>Event</th>
                <th>Type</th>
                <th>Transaction</th>
                <th>Status</th>
                <th>RabbitMQ</th>
                <th>Retries</th>
                <th>Created</th>
                <th />
              </tr>
            </thead>

            <tbody>
              {filteredEvents.map(event => {
                const brokerStatus = getBrokerStatus(event)
                const brokerTone = getBrokerTone(event)

                return (
                  <tr key={event.event_id}>
                    <td>
                      <div className="event-id-cell">
                        <div className="mono">
                          {event.event_id}
                        </div>

                        <div className="event-correlation">
                          {event.correlation_id || 'No correlation ID'}
                        </div>
                      </div>
                    </td>

                    <td>
                      <span className="event-type-text">
                        {formatEventType(event.event_type)}
                      </span>
                    </td>

                    <td className="mono">
                      {event.transaction_id || '—'}
                    </td>

                    <td>
                      <span
                        className={`event-chip status-${String(
                          event.status || 'UNKNOWN'
                        ).toLowerCase()}`}
                      >
                        {getStatusLabel(event.status)}
                      </span>
                    </td>

                    <td>
                      <span
                        className={`event-chip broker-${brokerTone}`}
                      >
                        {brokerStatus}
                      </span>
                    </td>

                    <td>
                      {Number(event.retry_count || 0)}
                    </td>

                    <td className="time-cell">
                      {formatDate(event.created_at)}
                    </td>

                    <td>
                      <button
                        type="button"
                        className="text-button event-view-button"
                        onClick={() =>
                          setSelectedEvent(event)
                        }
                      >
                        View
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {!loading && !filteredEvents.length && (
          <div className="empty-state compact">
            <div className="empty-title">
              No payment events found
            </div>

            <div className="empty-copy">
              Try changing the search or status filter.
            </div>
          </div>
        )}
      </div>

      {/* Event detail drawer */}
      {selectedEvent && (
        <div
          className="event-detail-overlay"
          onClick={() => setSelectedEvent(null)}
        >
          <aside
            className="event-detail-drawer"
            onClick={event => event.stopPropagation()}
          >
            <div className="event-detail-header">
              <div>
                <div className="event-detail-eyebrow">
                  EVENT DETAILS
                </div>

                <h3>
                  {formatEventType(
                    selectedEvent.event_type
                  )}
                </h3>

                <div className="mono">
                  {selectedEvent.event_id}
                </div>
              </div>

              <button
                type="button"
                className="event-detail-close"
                onClick={() => setSelectedEvent(null)}
                aria-label="Close event details"
              >
                ×
              </button>
            </div>

            <div className="event-detail-grid">
              <div>
                <span>Transaction</span>
                <strong className="mono">
                  {selectedEvent.transaction_id || '—'}
                </strong>
              </div>

              <div>
                <span>Status</span>
                <strong>
                  {selectedEvent.status || '—'}
                </strong>
              </div>

              <div>
                <span>Correlation ID</span>
                <strong className="mono">
                  {selectedEvent.correlation_id || '—'}
                </strong>
              </div>

              <div>
                <span>Retry count</span>
                <strong>
                  {Number(selectedEvent.retry_count || 0)}
                </strong>
              </div>

              <div>
                <span>Created</span>
                <strong>
                  {formatDate(selectedEvent.created_at)}
                </strong>
              </div>

              <div>
                <span>Processed</span>
                <strong>
                  {formatDate(selectedEvent.processed_at)}
                </strong>
              </div>

              <div>
                <span>RabbitMQ published</span>
                <strong>
                  {formatDate(
                    selectedEvent.broker_published_at
                  )}
                </strong>
              </div>

              <div>
                <span>Broker status</span>
                <strong>
                  {getBrokerStatus(selectedEvent)}
                </strong>
              </div>
            </div>

            {selectedEvent.error_message && (
              <div className="event-detail-section">
                <div className="event-detail-section-title">
                  Processing error
                </div>

                <pre>
                  {selectedEvent.error_message}
                </pre>
              </div>
            )}

            {selectedEvent.broker_error && (
              <div className="event-detail-section">
                <div className="event-detail-section-title">
                  Broker error
                </div>

                <pre>
                  {selectedEvent.broker_error}
                </pre>
              </div>
            )}
          </aside>
        </div>
      )}
    </section>
  )
}