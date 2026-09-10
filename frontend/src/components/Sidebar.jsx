const nav = [
  { id: 'overview', icon: '⌂', label: 'Overview' },
  { id: 'transactions', icon: '▤', label: 'Transactions' },
  { id: 'payment_links', icon: '↗', label: 'Payment Links' },
  { id: 'reconciliation', icon: '⇄', label: 'Reconciliation' },
  { id: 'refunds', icon: '↩', label: 'Refunds' },
  { id: 'retries', icon: '↻', label: 'Retries' },
  { id: 'investigations', icon: '!', label: 'Investigations' },
]

export default function Sidebar({ activePage, onNavigate, collapsed, onToggle }) {
  return (
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
      {/* Brand */}
      <div className="sidebar-brand">
        <div className="brand-mark">↔</div>

        {!collapsed && (
          <div className="brand-info">
            <div className="brand-name">PayReconcile</div>
            <div className="brand-sub">Payment Operations</div>
          </div>
        )}
      </div>

      {/* Workspace label */}
      {!collapsed && (
        <div className="sidebar-section-label">
          Workspace
        </div>
      )}

      {/* Navigation */}
      <nav className="sidebar-nav" aria-label="Primary navigation">
        {nav.map(item => (
          <button
            key={item.id}
            type="button"
            className={`nav-item ${activePage === item.id ? 'active' : ''}`}
            onClick={() => onNavigate(item.id)}
            title={collapsed ? item.label : ''}
          >
            <span className="nav-icon">{item.icon}</span>

            {!collapsed && (
              <span className="nav-label">
                {item.label}
              </span>
            )}
          </button>
        ))}
      </nav>

      {/* Footer */}
      {!collapsed && (
        <div className="sidebar-footer">
          <div className="simulation-pill">
            <span className="sim-dot" />
            Simulation Mode
          </div>

          <div className="sidebar-footer-copy">
            No real money movement
          </div>
        </div>
      )}

      {/* Collapse / Expand Button */}
      <button
        type="button"
        className="sidebar-toggle"
        onClick={onToggle}
        title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {collapsed ? '›' : '‹'}
      </button>
    </aside>
  )
}
