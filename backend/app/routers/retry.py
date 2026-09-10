import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, status
from pymongo.errors import PyMongoError, DuplicateKeyError

from backend.app.schemas import (
    RetryRequest,
    RetryResponse,
    RetryStatus
)
from backend.app.database import (
    get_transactions_collection,
    get_reconciliations_collection,
    get_retry_attempts_collection
)

router = APIRouter(
    prefix="/api/retry",
    tags=["Retry Workflow"]
)

MAX_RETRY_ATTEMPTS = 3

def generate_retry_reference() -> str:
    """Generate a unique human-readable retry reference (e.g. RETRY-A1B2C3D4E5F6)."""
    return f"RETRY-{uuid.uuid4().hex[:12].upper()}"


@router.get("/attempts")
def get_retry_attempts(
    retry_col=Depends(get_retry_attempts_collection),
    transactions_col=Depends(get_transactions_collection),
):
    """Return all recorded retry attempts for the admin dashboard."""
    try:
        attempts = list(
            retry_col.find({}, {"_id": 0}).sort("created_at", -1)
        )

        transaction_ids = list({
            attempt.get("transaction_id")
            for attempt in attempts
            if attempt.get("transaction_id")
        })

        transaction_docs = {}
        if transaction_ids:
            for txn in transactions_col.find(
                {"transaction_id": {"$in": transaction_ids}},
                {"_id": 0, "transaction_id": 1, "amount": 1, "currency": 1, "status": 1},
            ):
                transaction_docs[txn["transaction_id"]] = txn

        result = []
        for attempt in attempts:
            txn = transaction_docs.get(attempt.get("transaction_id"), {})
            result.append({
                **attempt,
                "amount": txn.get("amount"),
                "currency": txn.get("currency"),
                "transaction_status": txn.get("status"),
            })

        return result

    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while retrieving retry attempts: {str(err)}"
        )

@router.post("/process", response_model=RetryResponse, status_code=status.HTTP_200_OK)
def process_retry(
    payload: RetryRequest,
    transactions_col=Depends(get_transactions_collection),
    reconciliations_col=Depends(get_reconciliations_collection),
    retry_col=Depends(get_retry_attempts_collection)
):
    """
    Process a simulated payment retry for an eligible transaction.
    - STEP 1: Verify transaction exists (HTTP 404 if missing)
    - STEP 2: Verify transaction has been reconciled (HTTP 400 if missing)
    - STEP 3: Verify eligibility (action_required == RETRY)
    - STEP 4: Calculate attempt number & cap at MAX_RETRY_ATTEMPTS (3)
    - STEP 5: Prevent duplicate attempt processing
    - STEP 6: Execute simulated retry workflow (INITIATED -> PROCESSING -> SUCCESS)
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

    # 2. Verify reconciliation record exists
    try:
        rec_doc = reconciliations_col.find_one({"transaction_id": payload.transaction_id})
        if not rec_doc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transaction has not been reconciled"
            )
    except HTTPException:
        raise
    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while checking reconciliation: {str(err)}"
        )

    # 3. Verify retry eligibility
    action_req = rec_doc.get("action_required")
    if action_req != "RETRY":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transaction is not eligible for retry"
        )

    # 4. Check existing retry attempts
    try:
        existing_attempts = list(retry_col.find({"transaction_id": payload.transaction_id}).sort("attempt_number", 1))
    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while checking retry attempts: {str(err)}"
        )

    highest_attempt = max([attempt.get("attempt_number", 0) for attempt in existing_attempts], default=0)

    # Cap at MAX_RETRY_ATTEMPTS (3)
    if highest_attempt >= MAX_RETRY_ATTEMPTS:
        latest_attempt = existing_attempts[-1] if existing_attempts else {}
        return {
            "transaction_id": payload.transaction_id,
            "retry_reference": latest_attempt.get("retry_reference", generate_retry_reference()),
            "attempt_number": MAX_RETRY_ATTEMPTS,
            "status": RetryStatus.MAX_ATTEMPTS_REACHED.value,
            "reason": f"Maximum retry attempts reached ({MAX_RETRY_ATTEMPTS}/{MAX_RETRY_ATTEMPTS})",
            "created_at": latest_attempt.get("created_at", datetime.now(timezone.utc)),
            "completed_at": latest_attempt.get("completed_at")
        }

    next_attempt = highest_attempt + 1
    now = datetime.now(timezone.utc)
    retry_ref = generate_retry_reference()
    reason = rec_doc.get("reason", "Gateway payment successful but bank amount was not debited")

    # 5. Create retry document
    retry_doc = {
        "transaction_id": payload.transaction_id,
        "retry_reference": retry_ref,
        "attempt_number": next_attempt,
        "status": RetryStatus.SUCCESS.value,
        "reason": reason,
        "created_at": now,
        "completed_at": now
    }

    # 6. Save in retry_attempts collection
    try:
        retry_col.insert_one(retry_doc)
    except DuplicateKeyError:
        retry_ref = generate_retry_reference()
        retry_doc["retry_reference"] = retry_ref
        retry_col.insert_one(retry_doc)
    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while saving retry attempt: {str(err)}"
        )

    # 7. Mark the original payment as resolved after a successful retry.
    #    The retry itself succeeds in this simulation, so the transaction no
    #    longer needs a RETRY action.
    try:
        transactions_col.update_one(
            {"transaction_id": payload.transaction_id},
            {
                "$set": {
                    "status": "RESOLVED",
                    "updated_at": now,
                }
            }
        )

        reconciliations_col.update_one(
            {"transaction_id": payload.transaction_id},
            {
                "$set": {
                    "action_required": "NONE",
                    "resolved_at": now,
                }
            }
        )
    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Retry was recorded, but the transaction could not be marked resolved: {str(err)}"
        )

    return retry_doc
