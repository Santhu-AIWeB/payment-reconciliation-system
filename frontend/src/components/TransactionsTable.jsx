import StatusBadge from './StatusBadge'

function fmt(dateStr) {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  })
}

function fmtAmount(amount, currency) {
  if (amount == null) return '—'
  const symbol = currency === 'INR' ? '₹' : `${currency || ''} `
  return `${symbol}${Number(amount).toLocaleString('en-IN', {
    minimumFractionDigits: 2,
  })}`
}

export default function TransactionsTable({ transactions, onSelect }) {
  if (!transactions || transactions.length === 0) {
    return (
      <div className="empty-state compact">
        <div className="empty-title">No transactions found</div>
        <div className="empty-copy">Create or process a transaction to see it here.</div>
      </div>
    )
  }

  return (
    <div className="table-wrap">
      <table className="ops-table">
        <thead>
          <tr>
            <th>Transaction</th>
            <th>Amount</th>
            <th>Gateway</th>
            <th>Bank</th>
            <th>Reconciliation</th>
            <th>Action</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map(txn => (
            <tr key={txn.transaction_id} onClick={() => onSelect?.(txn.transaction_id)}>
              <td>
                <div className="txn-id">{txn.transaction_id}</div>
                <div className="txn-currency">{txn.currency}</div>
              </td>
              <td className="amount-cell">{fmtAmount(txn.amount, txn.currency)}</td>
              <td><StatusBadge value={txn.gateway?.status} /></td>
              <td><StatusBadge value={txn.bank?.status} /></td>
              <td><StatusBadge value={txn.reconciliation?.reconciliation_status} /></td>
              <td><StatusBadge value={txn.reconciliation?.action_required} /></td>
              <td className="time-cell">{fmt(txn.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
