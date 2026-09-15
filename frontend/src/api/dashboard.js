import axios from 'axios'

const API_BASE = 'https://payment-reconciliation-system-k1ry.onrender.com'

const api = axios.create({
  baseURL: `${API_BASE}/api/dashboard`,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

const auditApi = axios.create({
  baseURL: `${API_BASE}/api/audit`,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const fetchSummary = () =>
  api
    .get('/summary')
    .then(response => response.data)

export const fetchTransactions = () =>
  api
    .get('/transactions')
    .then(response => response.data)

export const fetchTransactionDetail = transactionId =>
  api
    .get(`/transactions/${transactionId}`)
    .then(response => response.data)

export const fetchTransactionAudit = transactionId =>
  auditApi
    .get(`/${transactionId}`)
    .then(response => response.data)