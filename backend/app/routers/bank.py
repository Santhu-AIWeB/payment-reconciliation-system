import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, status
from pymongo.errors import PyMongoError, DuplicateKeyError

from backend.app.schemas import (
    BankProcessRequest,
    BankProcessResponse,
    BankOutcome
)
from backend.app.database import (
    get_transactions_collection,
    get_bank_transactions_collection
)

router = APIRouter(
    prefix="/api/bank",
    tags=["Bank Simulator"]
)

def generate_bank_reference() -> str:
    """Generate a unique human-readable bank reference (e.g. BANK-A1B2C3D4E5F6)."""
    return f"BANK-{uuid.uuid4().hex[:12].upper()}"

BANK_RESPONSE_MESSAGES = {
    BankOutcome.DEBITED: "Amount debited successfully",
    BankOutcome.NOT_DEBITED: "Amount was not debited",
    BankOutcome.DELAYED: "Bank transaction is delayed"
}

@router.post("/process", response_model=BankProcessResponse, status_code=status.HTTP_200_OK)
def process_bank_transaction(
    payload: BankProcessRequest,
    transactions_col=Depends(get_transactions_collection),
    bank_col=Depends(get_bank_transactions_collection)
):
    """
    Simulate a customer bank processing event for a given transaction_id.
    - Verifies transaction existence in MongoDB
    - Generates a unique bank_reference
    - Records outcome in bank_transactions collection
    - Returns bank transaction result
    """
    # 1. Verify transaction exists
    try:
        txn = transactions_col.find_one({"transaction_id": payload.transaction_id})
        if not txn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transaction with ID '{payload.transaction_id}' not found."
            )
    except HTTPException:
        raise
    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while querying transaction: {str(err)}"
        )

    # 2. Extract transaction details & build bank document
    amount = txn.get("amount", 0.0)
    bank_ref = generate_bank_reference()
    now = datetime.now(timezone.utc)
    message = BANK_RESPONSE_MESSAGES.get(payload.outcome, "Bank operation processed")

    bank_doc = {
        "transaction_id": payload.transaction_id,
        "bank_reference": bank_ref,
        "amount": amount,
        "status": payload.outcome.value,
        "response_message": message,
        "created_at": now
    }

    # 3. Store in bank_transactions collection
    try:
        bank_col.insert_one(bank_doc)
    except DuplicateKeyError:
        bank_ref = generate_bank_reference()
        bank_doc["bank_reference"] = bank_ref
        bank_col.insert_one(bank_doc)
    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while saving bank transaction: {str(err)}"
        )

    return bank_doc
