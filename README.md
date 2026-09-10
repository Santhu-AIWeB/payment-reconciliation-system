# Payment Failure & Reconciliation System

A software system designed to detect and resolve inconsistencies between payment gateway transaction records and bank transaction records (e.g., payment gateway reports `FAILED`, but the bank reports `DEBITED`).

---

## Step 6B: Retry Workflow

In this step, we implemented the **Retry Workflow** (`POST /api/retry/process`). The retry engine verifies that a transaction has been processed by the **Reconciliation Engine** and is explicitly eligible for retry (`action_required == RETRY`).

It tracks attempt numbers (`1`, `2`, `3`) and caps retries at a maximum of **3 attempts** (`MAX_RETRY_ATTEMPTS = 3`). Subsequent attempts return status `MAX_ATTEMPTS_REACHED`.

Retry records are stored in the MongoDB **`retry_attempts`** collection.

---

## Project Structure

```text
payment-reconciliation-system/
├── backend/
│   └── app/
│       ├── routers/
│       │   ├── __init__.py
│       │   ├── bank.py
│       │   ├── gateway.py
│       │   ├── reconciliation.py
│       │   ├── refund.py
│       │   ├── retry.py
│       │   └── transactions.py
│       ├── __init__.py
│       ├── config.py
│       ├── database.py
│       ├── main.py
│       └── schemas.py
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Retry Decision Flow & Business Rules

```text
Transaction
    ↓
Gateway + Bank
    ↓
Reconciliation Engine
    ↓
action_required = RETRY
    ↓
Retry Workflow (Attempts 1, 2, 3) ➔ SUCCESS
    ↓ (Attempt 4+)
MAX_ATTEMPTS_REACHED
```

1. **Transaction & Reconciliation Check**:
   - `HTTP 404` if transaction does not exist.
   - `HTTP 400` ("Transaction has not been reconciled") if no reconciliation record exists.
2. **Eligibility Check**:
   - Must have `action_required == RETRY` (e.g. Gateway `SUCCESS` & Bank `NOT_DEBITED`, or Gateway `TIMEOUT` & Bank `NOT_DEBITED`).
   - Returns `HTTP 400` ("Transaction is not eligible for retry") if `action_required != RETRY`.
3. **Attempt Number Logic**:
   - First call ➔ `attempt_number: 1`
   - Second call ➔ `attempt_number: 2`
   - Third call ➔ `attempt_number: 3`
   - Fourth call+ ➔ returns `status: MAX_ATTEMPTS_REACHED` (attempt count remains capped at 3, no 4th database record created).

---

## API Endpoints Overview

- `POST /api/transactions`: Create transaction (`CREATED`).
- `POST /api/gateway/process`: Process gateway outcome (`SUCCESS`, `FAILED`, `TIMEOUT`).
- `POST /api/bank/process`: Process bank outcome (`DEBITED`, `NOT_DEBITED`, `DELAYED`).
- `POST /api/reconciliation/process`: Run reconciliation rules.
- `POST /api/refunds/process`: Process simulated refund workflow.
- `POST /api/retry/process`: Process simulated payment retry workflow (Max 3 attempts).

---

## Testing Retry Workflow with Postman (Step-by-Step)

### Step 1: Create a Transaction
- **POST** `http://127.0.0.1:8000/api/transactions`
- **Body**: `{"amount": 1500.0, "currency": "INR"}`
- Copy `transaction_id` (e.g. `"TXN-7D24362B6E5B"`).

### Step 2: Simulate Gateway Success
- **POST** `http://127.0.0.1:8000/api/gateway/process`
- **Body**: `{"transaction_id": "TXN-7D24362B6E5B", "outcome": "SUCCESS"}`

### Step 3: Simulate Bank NOT_DEBITED
- **POST** `http://127.0.0.1:8000/api/bank/process`
- **Body**: `{"transaction_id": "TXN-7D24362B6E5B", "outcome": "NOT_DEBITED"}`

### Step 4: Run Reconciliation Engine
- **POST** `http://127.0.0.1:8000/api/reconciliation/process`
- **Body**: `{"transaction_id": "TXN-7D24362B6E5B"}`
- **Expected**: `reconciliation_status == "MISMATCH"` and `action_required == "RETRY"`.

### Step 5: Process First Retry (Attempt 1)
- **POST** `http://127.0.0.1:8000/api/retry/process`
- **Body**: `{"transaction_id": "TXN-7D24362B6E5B"}`
- **Response (200 OK)**:
  ```json
  {
    "transaction_id": "TXN-7D24362B6E5B",
    "retry_reference": "RETRY-F8C282DBB5AF",
    "attempt_number": 1,
    "status": "SUCCESS",
    "reason": "Gateway payment successful but bank amount was not debited",
    "created_at": "2026-09-07T05:48:34.583589Z",
    "completed_at": "2026-09-07T05:48:34.583589Z"
  }
  ```

### Step 6: Process Attempts 2 & 3
- Send **POST** `http://127.0.0.1:8000/api/retry/process` again: `attempt_number = 2`.
- Send **POST** `http://127.0.0.1:8000/api/retry/process` again: `attempt_number = 3`.

### Step 7: Test Max Attempts Capping (Attempt 4)
- Send **POST** `http://127.0.0.1:8000/api/retry/process` a fourth time:
- **Response (200 OK)**:
  ```json
  {
    "transaction_id": "TXN-7D24362B6E5B",
    "retry_reference": "RETRY-636CB6A6E286",
    "attempt_number": 3,
    "status": "MAX_ATTEMPTS_REACHED",
    "reason": "Maximum retry attempts reached (3/3)",
    "created_at": "2026-09-07T05:48:34.596000Z",
    "completed_at": "2026-09-07T05:48:34.596000Z"
  }
  ```

---

## 🔗 Architecture Summary (Steps 1 to 6B Complete)

With Step 6B complete, the full transaction reconciliation and resolution lifecycle is established:
1. **Transaction Lifecycle**: Creation ➔ Gateway Simulation ➔ Bank Simulation.
2. **Reconciliation**: Compare gateway & bank logs ➔ determine `action_required`.
3. **Resolution Pipelines**:
   - `REFUND` ➔ **Step 6A (Refund Workflow)**.
   - `RETRY` ➔ **Step 6B (Retry Workflow)**.
