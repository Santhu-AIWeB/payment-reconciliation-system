# Payment Failure & Reconciliation System

A full-stack payment reconciliation simulation that detects inconsistencies between payment gateway results and bank transaction records, then routes each transaction into an appropriate resolution workflow such as **refund, retry, investigation, or wait**.

The project also includes merchant payment links, a customer payment page, audit trail, transaction timeline, admin dashboard, AI-based anomaly detection, and Dockerized deployment.

> **Important:** This is a simulation project. It does not connect to real banks, payment gateways, cards, UPI, or move real money.

## 🎯 Problem Statement

Payment systems can encounter situations where the payment gateway and bank records disagree.

For example:
- Gateway says `FAILED`
- Bank says `DEBITED`

The customer may have been charged even though the payment appears failed at the gateway.

A reconciliation system needs to:
1. Collect gateway and bank outcomes.
2. Compare them.
3. Detect mismatches and pending states.
4. Decide what action is required.
5. Execute the appropriate simulated resolution.
6. Keep an audit trail.
7. Highlight unusual transactions for investigation.

## 🚀 Key Features

### Payment Processing Simulation
- Transaction creation
- Payment gateway simulator
- Bank transaction simulator
- Gateway outcomes: `SUCCESS`, `FAILED`, `TIMEOUT`
- Bank outcomes: `DEBITED`, `NOT_DEBITED`, `DELAYED`

### Reconciliation Engine

| Gateway | Bank | Result | Action |
|---|---|---|---|
| `FAILED` | `DEBITED` | `MISMATCH` | `REFUND` |
| `SUCCESS` | `NOT_DEBITED` | `MISMATCH` | `RETRY` |
| `TIMEOUT` | `DEBITED` | `MISMATCH` | `INVESTIGATE` |
| `TIMEOUT` | `NOT_DEBITED` | `PENDING` | `RETRY` |
| `SUCCESS` | `DELAYED` | `PENDING` | `WAIT` |

### 💰 Refund Workflow

`FAILED + DEBITED → MISMATCH → REFUND`

The system provides a simulated refund workflow and records the result for the transaction.

### 🔄 Retry Workflow

Retry-eligible transactions can be processed through simulated retry attempts. The maximum is **3 attempts**.

```text
Transaction
     ↓
Gateway + Bank
     ↓
Reconciliation
     ↓
action_required = RETRY
     ↓
Attempt 1 → Attempt 2 → Attempt 3
     ↓
MAX_ATTEMPTS_REACHED
```

### 🔎 Investigation Workflow

For cases such as `TIMEOUT + DEBITED`, reconciliation routes the transaction to `INVESTIGATE`. The admin interface provides transaction details and AI investigation information.

### 🤖 AI Anomaly Detection

The project uses **Scikit-learn Isolation Forest** when sufficient historical data is available, with a rule-based fallback otherwise.

Features include:
- Payment amount
- Gateway failure
- Gateway timeout
- Bank debited
- Bank delayed
- Reconciliation mismatch
- Reconciliation pending
- Refund action
- Retry action
- Investigation action

The AI endpoint provides an anomaly result, risk/anomaly score, risk level, model type, training sample count, explanation, and recommended investigation priority.

> The AI score is an anomaly/risk score, not a probability that a payment will fail.

### 🔗 Merchant Payment Links

```text
Merchant
   ↓
Create Payment Link
   ↓
Customer Opens Link
   ↓
Payment Page
   ↓
Gateway + Bank Simulation
   ↓
Reconciliation
   ↓
Customer Result
```

### 👤 Customer Experience
- Payment-link based flow
- Customer payment page
- Payment result page
- Exception handling
- Transaction status information

### 📊 Admin Dashboard
- Transaction statistics
- Matched, mismatched, and pending payments
- Refunds
- Retry attempts
- Investigations
- Payment links
- Transaction details
- Audit trail
- Transaction timeline
- AI investigation drawer

### 🧾 Audit Trail

A transaction lifecycle can be inspected as:

```text
CREATED
  ↓
GATEWAY PROCESSED
  ↓
BANK PROCESSED
  ↓
RECONCILIATION
  ↓
MATCHED / MISMATCH / PENDING
  ↓
REFUND / RETRY / INVESTIGATE / WAIT
```

## 🏗️ Architecture

```text
                         ┌──────────────────────┐
                         │      React UI        │
                         │   Admin + Customer   │
                         └──────────┬───────────┘
                                    │ REST API
                                    ▼
                         ┌──────────────────────┐
                         │      FastAPI         │
                         │      Backend         │
                         └──────────┬───────────┘
                                    │
                ┌───────────────────┼───────────────────┐
                ▼                   ▼                   ▼
       ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
       │ Gateway        │  │ Bank           │  │ Reconciliation │
       │ Simulator      │  │ Simulator      │  │ Engine         │
       └────────────────┘  └────────────────┘  └───────┬────────┘
                                                       │
                                      ┌────────────────┼────────────────┐
                                      ▼                ▼                ▼
                                  Refund            Retry         Investigation
                                      │                │                │
                                      └────────────────┼────────────────┘
                                                       ▼
                                            ┌────────────────────┐
                                            │   AI Anomaly       │
                                            │     Detection      │
                                            └─────────┬──────────┘
                                                      ▼
                                            ┌────────────────────┐
                                            │      MongoDB       │
                                            └────────────────────┘
```

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite |
| Backend | Python + FastAPI |
| Database | MongoDB + PyMongo |
| Validation | Pydantic |
| AI/ML | Scikit-learn + NumPy |
| API Testing | Postman + Python automated test |
| API Documentation | FastAPI Swagger/OpenAPI |
| Containerization | Docker |
| Orchestration | Docker Compose |

## 📁 Project Structure

```text
payment-reconciliation-system/
├── backend/
│   ├── .dockerignore
│   ├── Dockerfile
│   └── app/
│       ├── __init__.py
│       ├── ai_service.py
│       ├── config.py
│       ├── database.py
│       ├── main.py
│       ├── schemas.py
│       └── routers/
│           ├── __init__.py
│           ├── ai.py
│           ├── audit.py
│           ├── bank.py
│           ├── dashboard.py
│           ├── gateway.py
│           ├── payment_links.py
│           ├── reconciliation.py
│           ├── refund.py
│           ├── retry.py
│           └── transactions.py
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── package-lock.json
│   ├── vite.config.js
│   ├── public/
│   └── src/
├── docker-compose.yml
├── full_system_test.py
├── seed_ml_history.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## 🔌 API Endpoints

```text
POST /api/transactions
POST /api/gateway/process
POST /api/bank/process
POST /api/reconciliation/process
POST /api/refunds/process
POST /api/retry/process

GET  /api/dashboard/summary
GET  /api/dashboard/transactions
GET  /api/ai/analyze/{transaction_id}
```

## 🐳 Run with Docker

### Prerequisites
- Docker Desktop
- Git

### Start

```bash
docker compose up -d --build
```

Services:

```text
Frontend  → http://localhost:5173
Backend   → http://localhost:8000
Swagger   → http://localhost:8000/docs
MongoDB   → localhost:27017
```

Check containers:

```bash
docker compose ps
```

Stop:

```bash
docker compose down
```

> Do not use `docker compose down -v` unless you intentionally want to remove the MongoDB Docker volume and its stored simulated data.

## ⚙️ Environment Variables

Create `.env` from `.env.example`:

```env
MONGODB_URI=mongodb://localhost:27017
DB_NAME=payment_reconciliation_db
```

`.env` is intentionally ignored by Git.

Never commit real credentials, API keys, bank credentials, payment gateway secrets, card information, or other sensitive data.

## 🧪 Automated Full-System Testing

The repository includes:

```text
full_system_test.py
```

It verifies five complete scenarios:

```text
FAILED + DEBITED
→ MISMATCH
→ REFUND
→ COMPLETED

SUCCESS + NOT_DEBITED
→ MISMATCH
→ RETRY
→ SUCCESS

TIMEOUT + DEBITED
→ MISMATCH
→ INVESTIGATE

TIMEOUT + NOT_DEBITED
→ PENDING
→ RETRY
→ SUCCESS

SUCCESS + DELAYED
→ PENDING
→ WAIT
```

Run:

```bash
python full_system_test.py
```

The suite also checks the AI endpoint, Isolation Forest availability, refund/retry workflows, and dashboard transaction details.

## 📈 Validation Result

The complete system test was successfully executed across all five scenarios.

Validated components include:
- Transaction creation
- Gateway simulation
- Bank simulation
- Reconciliation
- Refund workflow
- Retry workflow
- Investigation routing
- Pending handling
- AI anomaly endpoint
- Isolation Forest model
- Dashboard transaction details
- Refund visibility
- Retry visibility

```text
RESULT: ALL TESTS PASSED
```

## 🔐 Security & Scope

This is a **simulation** for learning, portfolio demonstration, and system-design practice.

It does **not**:
- Move real money
- Connect to real banks
- Connect to real payment gateways
- Process real card numbers
- Process real UPI credentials
- Store real financial credentials
- Initiate real refunds
- Initiate real bank transfers

All gateway, bank, refund, and retry operations are simulated inside the application.

## 🎓 Learning Outcomes

This project demonstrates practical experience with:
- Full-stack application development
- REST API design
- FastAPI
- React
- MongoDB
- Payment reconciliation concepts
- Transaction state management
- Failure handling
- Retry strategies
- Refund workflows
- Audit logging
- Docker and Docker Compose
- API testing
- Machine-learning anomaly detection
- Integrating AI into an operational dashboard

## 🔮 Future Improvements

Potential production-oriented extensions:
- Real payment-provider adapters
- Message queues for asynchronous reconciliation
- Scheduled reconciliation jobs
- Idempotency keys across payment operations
- Distributed locking
- Role-based access control
- Authentication and authorization
- Observability and metrics
- Alerting
- Model monitoring and retraining pipelines
- Cloud deployment
- Automated CI/CD
- Automated security scanning

These are future extensions and are not part of the current simulation.

## 👨‍💻 Author

**V. Santosh**

B.Tech — Computer Science & Engineering (AI/ML)

## 📄 License

This project is intended for educational and portfolio purposes.
