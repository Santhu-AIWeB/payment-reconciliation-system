import os

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


# =========================================================
# Configuration
# =========================================================

BACKEND_URL = os.getenv(
    "BACKEND_URL",
    "http://localhost:8000"
)

BANK_SERVER_URL = os.getenv(
    "BANK_SERVER_URL",
    "http://localhost:8001"
)


# =========================================================
# FastAPI
# =========================================================

app = FastAPI(
    title="Payment Gateway Server",
    version="1.0.0",
    description=(
        "Separate simulated payment gateway for the "
        "payment reconciliation system."
    ),
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# Customer Payment Request
# =========================================================

class PaymentRequest(BaseModel):
    amount: float = Field(gt=0)
    currency: str = "INR"
    account_id: str = "DUMMY-1001"


# =========================================================
# Developer Test Request
# =========================================================

class TestPaymentRequest(BaseModel):
    amount: float = Field(gt=0)
    currency: str = "INR"
    account_id: str = "DUMMY-1001"

    gateway_outcome: str = "SUCCESS"
    bank_outcome: str = "DEBITED"


# =========================================================
# HTTP Helpers
# =========================================================

def post_json(
    url: str,
    payload: dict,
    timeout: int = 10,
):
    """
    Send a POST request to another service and return JSON.
    """

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=timeout,
        )

    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Service unavailable: {url}. "
                f"Error: {exc}"
            ),
        )

    try:
        data = response.json()

    except ValueError:
        data = {
            "message": response.text
        }

    if not response.ok:
        raise HTTPException(
            status_code=response.status_code,
            detail=data,
        )

    return data


def get_json(
    url: str,
    timeout: int = 10,
):
    """
    Send a GET request to another service and return JSON.
    """

    try:
        response = requests.get(
            url,
            timeout=timeout,
        )

    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Service unavailable: {url}. "
                f"Error: {exc}"
            ),
        )

    try:
        data = response.json()

    except ValueError:
        data = {
            "message": response.text
        }

    if not response.ok:
        raise HTTPException(
            status_code=response.status_code,
            detail=data,
        )

    return data


# =========================================================
# Common Payment Processor
# =========================================================

def execute_payment(
    amount: float,
    currency: str,
    account_id: str,
    gateway_outcome: str,
    bank_outcome: str,
):
    """
    Complete the synchronous part of the payment lifecycle.

    1. Create transaction in Main Backend
    2. Process payment in separate Dummy Bank
    3. Record Gateway result in Main Backend
    4. Sync Bank result to Main Backend

    Reconciliation is NOT called directly here.

    The BANK_PROCESSED event is consumed by the
    RabbitMQ worker, which triggers reconciliation.
    """

    currency = currency.upper()
    gateway_outcome = gateway_outcome.upper()
    bank_outcome = bank_outcome.upper()

    # -----------------------------------------------------
    # Validate Gateway Outcome
    # -----------------------------------------------------

    allowed_gateway_outcomes = {
        "SUCCESS",
        "FAILED",
        "TIMEOUT",
    }

    if gateway_outcome not in allowed_gateway_outcomes:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid gateway outcome. "
                "Allowed values: SUCCESS, FAILED, TIMEOUT."
            ),
        )

    # -----------------------------------------------------
    # Validate Bank Outcome
    # -----------------------------------------------------

    allowed_bank_outcomes = {
        "DEBITED",
        "NOT_DEBITED",
        "DELAYED",
    }

    if bank_outcome not in allowed_bank_outcomes:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid bank outcome. "
                "Allowed values: DEBITED, NOT_DEBITED, DELAYED."
            ),
        )

    # =====================================================
    # STEP 1
    # Create Transaction
    # =====================================================

    transaction = post_json(
        f"{BACKEND_URL}/api/transactions",
        {
            "amount": round(amount, 2),
            "currency": currency,
        },
    )

    transaction_id = transaction["transaction_id"]

    # =====================================================
    # STEP 2
    # Process Payment in Dummy Bank
    # =====================================================

    bank_result = post_json(
        f"{BANK_SERVER_URL}/api/bank/debit",
        {
            "transaction_id": transaction_id,
            "account_id": account_id,
            "amount": round(amount, 2),
            "currency": currency,
            "outcome": bank_outcome,
        },
    )

    # =====================================================
    # STEP 3
    # Record Gateway Result in Main Backend
    # =====================================================

    gateway_result = post_json(
        f"{BACKEND_URL}/api/gateway/process",
        {
            "transaction_id": transaction_id,
            "outcome": gateway_outcome,
        },
    )

    # =====================================================
    # STEP 4
    # Sync Bank Result to Main Backend
    # =====================================================

    bank_sync_result = post_json(
        f"{BACKEND_URL}/api/bank/process",
        {
            "transaction_id": transaction_id,
            "outcome": bank_outcome,
        },
    )

    # =====================================================
    # STEP 5
    # Reconciliation is EVENT-DRIVEN
    # =====================================================
    #
    # Do NOT call /api/reconciliation/process here.
    #
    # bank.py publishes BANK_PROCESSED.
    # RabbitMQ worker consumes it and triggers reconciliation.
    #
    # =====================================================

    return {
        "transaction_id": transaction_id,
        "amount": round(amount, 2),
        "currency": currency,

        "gateway": gateway_result,

        "bank": bank_result,

        "bank_sync": bank_sync_result,

        "reconciliation": {
            "status": "PENDING",
            "message": (
                "Payment processing completed. "
                "Reconciliation is being processed asynchronously."
            ),
        },
    }


# =========================================================
# Health Check
# =========================================================

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "payment-gateway-server",
    }


# =========================================================
# NORMAL CUSTOMER PAYMENT
# =========================================================

@app.post("/api/gateway/pay")
def customer_payment(payload: PaymentRequest):
    """
    Normal customer payment.

    Customer does NOT choose gateway or bank outcome.

    Internally:
        Gateway -> SUCCESS
        Bank    -> DEBITED

    Reconciliation is handled asynchronously by RabbitMQ.
    """

    return execute_payment(
        amount=payload.amount,
        currency=payload.currency,
        account_id=payload.account_id,
        gateway_outcome="SUCCESS",
        bank_outcome="DEBITED",
    )


# =========================================================
# DEVELOPER / TEST PAYMENT
# =========================================================

@app.post("/api/gateway/test-pay")
def test_payment(payload: TestPaymentRequest):
    """
    Developer testing endpoint.

    Allows controlled simulation of different
    Gateway and Bank outcomes.
    """

    return execute_payment(
        amount=payload.amount,
        currency=payload.currency,
        account_id=payload.account_id,
        gateway_outcome=payload.gateway_outcome,
        bank_outcome=payload.bank_outcome,
    )


# =========================================================
# TRANSACTION STATUS
# =========================================================

@app.get("/api/gateway/transaction/{transaction_id}")
def get_transaction_status(transaction_id: str):
    """
    Return the latest asynchronous payment status.

    The Gateway reads the existing event stream from the
    Main Backend so the customer frontend can poll the
    payment status without talking directly to the backend.
    """

    events = get_json(
        f"{BACKEND_URL}/api/events?limit=500"
    )

    transaction_events = [
        event
        for event in events
        if event.get("transaction_id") == transaction_id
    ]

    if not transaction_events:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No payment events found for "
                f"transaction '{transaction_id}'."
            ),
        )

    reconciliation_event = next(
        (
            event
            for event in transaction_events
            if event.get("event_type")
            == "RECONCILIATION_REQUIRED"
        ),
        None,
    )

    return {
        "transaction_id": transaction_id,
        "reconciliation": (
            reconciliation_event.get("payload")
            if reconciliation_event
            else None
        ),
        "reconciliation_event_status": (
            reconciliation_event.get("status")
            if reconciliation_event
            else "PENDING"
        ),
    }


# =========================================================
# Account Balance Proxy
# =========================================================

@app.get("/api/gateway/account/{account_id}")
def get_account(account_id: str):

    try:
        response = requests.get(
            f"{BANK_SERVER_URL}/api/bank/accounts/{account_id}",
            timeout=10,
        )

    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Bank Server unavailable: {exc}",
        )

    try:
        data = response.json()

    except ValueError:
        data = {
            "message": response.text
        }

    if not response.ok:
        raise HTTPException(
            status_code=response.status_code,
            detail=data,
        )

    return data