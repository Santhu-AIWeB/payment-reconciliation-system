import os
import uuid
from datetime import datetime, timezone
from enum import Enum

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from pymongo import ASCENDING, MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError


# =========================================================
# Configuration
# =========================================================

MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb://localhost:27017"
)

DB_NAME = os.getenv(
    "DB_NAME",
    "payment_reconciliation_db"
)

BANK_ACCOUNTS_COLLECTION = "bank_accounts"
BANK_TRANSACTIONS_COLLECTION = "bank_transactions"


# =========================================================
# MongoDB
# =========================================================

client = MongoClient(
    MONGODB_URI,
    tz_aware=True,
)

db = client[DB_NAME]

accounts_col = db[BANK_ACCOUNTS_COLLECTION]
transactions_col = db[BANK_TRANSACTIONS_COLLECTION]


# =========================================================
# FastAPI
# =========================================================

app = FastAPI(
    title="Dummy Bank Server",
    version="1.0.0",
    description=(
        "Standalone simulated bank server for the "
        "payment reconciliation system. "
        "No real money movement occurs."
    ),
)


# =========================================================
# Models
# =========================================================

class BankOutcome(str, Enum):
    DEBITED = "DEBITED"
    NOT_DEBITED = "NOT_DEBITED"
    DELAYED = "DELAYED"


class CreateAccountRequest(BaseModel):
    account_id: str = Field(min_length=1)
    customer_name: str = Field(min_length=1)
    currency: str = Field(
        default="INR",
        min_length=3,
        max_length=3,
    )
    initial_balance: float = Field(ge=0)


class DebitRequest(BaseModel):
    transaction_id: str = Field(min_length=1)
    account_id: str = Field(
        default="DUMMY-1001",
        min_length=1,
    )
    amount: float = Field(gt=0)
    currency: str = Field(
        default="INR",
        min_length=3,
        max_length=3,
    )
    outcome: BankOutcome = BankOutcome.DEBITED


# =========================================================
# Helpers
# =========================================================

def generate_bank_reference() -> str:
    return f"BANK-{uuid.uuid4().hex[:12].upper()}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# =========================================================
# Demo Account
# =========================================================

def ensure_demo_account() -> None:
    """
    Create the default demo account only when it does not exist.

    Existing account balance is never reset.
    """

    existing = accounts_col.find_one(
        {
            "account_id": "DUMMY-1001"
        },
        {
            "_id": 1
        },
    )

    if existing:
        return

    now = utc_now()

    account = {
        "account_id": "DUMMY-1001",
        "account_name": "Demo Customer",
        "currency": "INR",
        "balance": 10000.00,
        "status": "ACTIVE",
        "created_at": now,
        "updated_at": now,
    }

    try:
        accounts_col.insert_one(account)
    except DuplicateKeyError:
        pass


# =========================================================
# Indexes
# =========================================================

def ensure_indexes() -> None:

    # One unique record per bank account
    accounts_col.create_index(
        [("account_id", ASCENDING)],
        unique=True,
    )

    # Every generated bank reference must be unique
    transactions_col.create_index(
        [("bank_reference", ASCENDING)],
        unique=True,
    )

    # NON-UNIQUE transaction_id index.
    #
    # The existing project database may already contain
    # duplicate bank transaction records for a transaction.
    # Therefore this index must not be unique.
    #
    # Duplicate processing is handled by the application
    # logic in debit_account().
    transactions_col.create_index(
        [("transaction_id", ASCENDING)],
    )


# =========================================================
# Startup
# =========================================================

@app.on_event("startup")
def startup_event():

    ensure_indexes()

    ensure_demo_account()


# =========================================================
# Health Check
# =========================================================

@app.get("/health")
def health():

    try:
        client.admin.command("ping")

        return {
            "status": "ok",
            "service": "dummy-bank-server",
            "database": DB_NAME,
        }

    except PyMongoError as exc:

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Bank database unavailable: {exc}"
            ),
        )


# =========================================================
# Get All Bank Accounts
# =========================================================

@app.get("/api/bank/accounts")
def get_accounts():

    try:

        accounts = accounts_col.find(
            {},
            {
                "_id": 0
            }
        ).sort(
            "created_at",
            ASCENDING,
        )

        return {
            "accounts": list(accounts)
        }

    except PyMongoError as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Unable to retrieve bank accounts: {exc}"
            ),
        )


# =========================================================
# Create Bank Account
# =========================================================

@app.post(
    "/api/bank/accounts",
    status_code=status.HTTP_201_CREATED,
)
def create_account(
    payload: CreateAccountRequest,
):

    account_id = payload.account_id.strip()
    customer_name = payload.customer_name.strip()
    currency = payload.currency.upper()

    if not account_id:
        raise HTTPException(
            status_code=400,
            detail="Account ID cannot be empty.",
        )

    if not customer_name:
        raise HTTPException(
            status_code=400,
            detail="Customer name cannot be empty.",
        )

    # -----------------------------------------------------
    # Check existing account
    # -----------------------------------------------------

    existing = accounts_col.find_one(
        {
            "account_id": account_id
        }
    )

    if existing:

        raise HTTPException(
            status_code=409,
            detail=(
                f"Bank account '{account_id}' already exists."
            ),
        )

    # -----------------------------------------------------
    # Create account
    # -----------------------------------------------------

    now = utc_now()

    account = {
        "account_id": account_id,
        "account_name": customer_name,
        "currency": currency,
        "balance": round(
            payload.initial_balance,
            2,
        ),
        "status": "ACTIVE",
        "created_at": now,
        "updated_at": now,
    }

    try:

        accounts_col.insert_one(account)

    except DuplicateKeyError:

        raise HTTPException(
            status_code=409,
            detail=(
                f"Bank account '{account_id}' already exists."
            ),
        )

    except PyMongoError as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Unable to create bank account: {exc}"
            ),
        )

    account.pop("_id", None)

    return account


# =========================================================
# Get One Bank Account
# =========================================================

@app.get("/api/bank/accounts/{account_id}")
def get_account(
    account_id: str,
):

    try:

        account = accounts_col.find_one(
            {
                "account_id": account_id
            },
            {
                "_id": 0
            },
        )

        if not account:

            raise HTTPException(
                status_code=404,
                detail=(
                    f"Bank account '{account_id}' not found."
                ),
            )

        return account

    except HTTPException:
        raise

    except PyMongoError as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Unable to retrieve bank account: {exc}"
            ),
        )


# =========================================================
# Debit Bank Account
# =========================================================

@app.post("/api/bank/debit")
def debit_account(
    payload: DebitRequest,
):

    currency = payload.currency.upper()

    amount = round(
        payload.amount,
        2,
    )

    # -----------------------------------------------------
    # Find account
    # -----------------------------------------------------

    account = accounts_col.find_one(
        {
            "account_id": payload.account_id
        }
    )

    if not account:

        raise HTTPException(
            status_code=404,
            detail=(
                f"Bank account '{payload.account_id}' "
                f"not found."
            ),
        )

    # -----------------------------------------------------
    # Currency check
    # -----------------------------------------------------

    if account["currency"].upper() != currency:

        raise HTTPException(
            status_code=400,
            detail="Currency mismatch.",
        )

    # -----------------------------------------------------
    # Prevent duplicate transaction
    #
    # This prevents the same transaction from being
    # debited more than once.
    # -----------------------------------------------------

    existing_transaction = transactions_col.find_one(
        {
            "transaction_id": payload.transaction_id
        },
        {
            "_id": 0
        },
    )

    if existing_transaction:

        return {
            "transaction_id": payload.transaction_id,
            "account_id": payload.account_id,
            "bank_reference": existing_transaction.get(
                "bank_reference"
            ),
            "amount": existing_transaction.get(
                "amount"
            ),
            "currency": existing_transaction.get(
                "currency"
            ),
            "status": existing_transaction.get(
                "status"
            ),
            "balance_before": existing_transaction.get(
                "balance_before"
            ),
            "balance_after": existing_transaction.get(
                "balance_after"
            ),
            "message": (
                "Transaction was already processed."
            ),
        }

    # =====================================================
    # NOT_DEBITED
    # =====================================================

    if payload.outcome == BankOutcome.NOT_DEBITED:

        bank_reference = generate_bank_reference()
        now = utc_now()

        balance = round(
            account["balance"],
            2,
        )

        bank_transaction = {
            "transaction_id": payload.transaction_id,
            "account_id": payload.account_id,
            "bank_reference": bank_reference,
            "amount": amount,
            "currency": currency,
            "status": BankOutcome.NOT_DEBITED.value,
            "balance_before": balance,
            "balance_after": balance,
            "response_message": (
                "Amount was not debited."
            ),
            "created_at": now,
        }

        try:

            transactions_col.insert_one(
                bank_transaction
            )

        except DuplicateKeyError:

            existing = transactions_col.find_one(
                {
                    "transaction_id":
                    payload.transaction_id
                },
                {
                    "_id": 0
                },
            )

            return {
                "transaction_id": payload.transaction_id,
                "status": (
                    existing.get("status")
                    if existing
                    else "NOT_DEBITED"
                ),
                "message": (
                    "Transaction was already processed."
                ),
            }

        return {
            "transaction_id": payload.transaction_id,
            "account_id": payload.account_id,
            "bank_reference": bank_reference,
            "amount": amount,
            "currency": currency,
            "status": (
                BankOutcome.NOT_DEBITED.value
            ),
            "balance_before": balance,
            "balance_after": balance,
            "message": (
                "Payment was not debited "
                "from the bank account."
            ),
        }

    # =====================================================
    # DELAYED
    # =====================================================

    if payload.outcome == BankOutcome.DELAYED:

        bank_reference = generate_bank_reference()
        now = utc_now()

        balance = round(
            account["balance"],
            2,
        )

        bank_transaction = {
            "transaction_id": payload.transaction_id,
            "account_id": payload.account_id,
            "bank_reference": bank_reference,
            "amount": amount,
            "currency": currency,
            "status": BankOutcome.DELAYED.value,
            "balance_before": balance,
            "balance_after": balance,
            "response_message": (
                "Bank transaction is delayed."
            ),
            "created_at": now,
        }

        try:

            transactions_col.insert_one(
                bank_transaction
            )

        except DuplicateKeyError:

            existing = transactions_col.find_one(
                {
                    "transaction_id":
                    payload.transaction_id
                },
                {
                    "_id": 0
                },
            )

            return {
                "transaction_id": payload.transaction_id,
                "status": (
                    existing.get("status")
                    if existing
                    else "DELAYED"
                ),
                "message": (
                    "Transaction was already processed."
                ),
            }

        return {
            "transaction_id": payload.transaction_id,
            "account_id": payload.account_id,
            "bank_reference": bank_reference,
            "amount": amount,
            "currency": currency,
            "status": (
                BankOutcome.DELAYED.value
            ),
            "balance_before": balance,
            "balance_after": balance,
            "message": (
                "Bank processing is delayed. "
                "Amount has not been debited yet."
            ),
        }

    # =====================================================
    # DEBITED
    # =====================================================

    updated_account = accounts_col.find_one_and_update(
        {
            "account_id": payload.account_id,
            "balance": {
                "$gte": amount
            },
        },
        {
            "$inc": {
                "balance": -amount
            },
            "$set": {
                "updated_at": utc_now()
            },
        },
        return_document=ReturnDocument.AFTER,
    )

    if not updated_account:

        raise HTTPException(
            status_code=400,
            detail=(
                "Insufficient bank balance."
            ),
        )

    balance_after = round(
        updated_account["balance"],
        2,
    )

    balance_before = round(
        balance_after + amount,
        2,
    )

    bank_reference = generate_bank_reference()
    now = utc_now()

    bank_transaction = {
        "transaction_id": payload.transaction_id,
        "account_id": payload.account_id,
        "bank_reference": bank_reference,
        "amount": amount,
        "currency": currency,
        "status": BankOutcome.DEBITED.value,
        "balance_before": balance_before,
        "balance_after": balance_after,
        "response_message": (
            "Amount debited successfully."
        ),
        "created_at": now,
    }

    try:

        transactions_col.insert_one(
            bank_transaction
        )

    except DuplicateKeyError:

        raise HTTPException(
            status_code=409,
            detail=(
                "Transaction was processed concurrently."
            ),
        )

    return {
        "transaction_id": payload.transaction_id,
        "account_id": payload.account_id,
        "bank_reference": bank_reference,
        "amount": amount,
        "currency": currency,
        "status": BankOutcome.DEBITED.value,
        "balance_before": balance_before,
        "balance_after": balance_after,
        "message": (
            "Payment amount debited successfully."
        ),
    }


# =========================================================
# Get Bank Transaction
# =========================================================

@app.get(
    "/api/bank/transactions/{transaction_id}"
)
def get_bank_transaction(
    transaction_id: str,
):

    try:

        transaction = transactions_col.find_one(
            {
                "transaction_id": transaction_id
            },
            {
                "_id": 0
            },
            sort=[
                ("created_at", -1)
            ],
        )

        if not transaction:

            raise HTTPException(
                status_code=404,
                detail=(
                    "Bank transaction not found."
                ),
            )

        return transaction

    except HTTPException:
        raise

    except PyMongoError as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Unable to retrieve bank transaction: {exc}"
            ),
        )