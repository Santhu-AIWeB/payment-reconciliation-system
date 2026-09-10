import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, status
from pymongo.errors import PyMongoError, DuplicateKeyError

from backend.app.schemas import (
    RefundRequest,
    RefundResponse,
    RefundStatus
)
from backend.app.database import (
    get_transactions_collection,
    get_reconciliations_collection,
    get_refunds_collection
)

router = APIRouter(
    prefix="/api/refunds",
    tags=["Refund Workflow"]
)

def generate_refund_reference() -> str:
    """Generate a unique human-readable refund reference (e.g. REFUND-A1B2C3D4E5F6)."""
    return f"REFUND-{uuid.uuid4().hex[:12].upper()}"

@router.post("/process", response_model=RefundResponse, status_code=status.HTTP_200_OK)
def process_refund(
    payload: RefundRequest,
    transactions_col=Depends(get_transactions_collection),
    reconciliations_col=Depends(get_reconciliations_collection),
    refunds_col=Depends(get_refunds_collection)
):
    """
    Process a simulated refund for an eligible reconciled transaction.
    - STEP 1: Verify transaction exists (HTTP 404 if missing)
    - STEP 2: Verify transaction has been reconciled (HTTP 400 if missing)
    - STEP 3: Verify eligibility (reconciliation_status=MISMATCH & action_required=REFUND)
    - STEP 4: Prevent duplicate refunds (returns DUPLICATE status if present)
    - STEP 5: Execute simulated refund workflow (INITIATED -> PROCESSING -> COMPLETED)
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

    # 3. Verify refund eligibility
    rec_status = rec_doc.get("reconciliation_status")
    action_req = rec_doc.get("action_required")

    if rec_status != "MISMATCH" or action_req != "REFUND":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transaction is not eligible for refund"
        )

    # 4. Check for duplicate refund
    try:
        existing_refund = refunds_col.find_one({"transaction_id": payload.transaction_id})
        if existing_refund:
            return {
                "transaction_id": payload.transaction_id,
                "refund_reference": existing_refund.get("refund_reference"),
                "amount": existing_refund.get("amount"),
                "status": RefundStatus.DUPLICATE.value,
                "reason": "Refund has already been initiated for this transaction",
                "created_at": existing_refund.get("created_at"),
                "completed_at": existing_refund.get("completed_at")
            }
    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while checking duplicate refund: {str(err)}"
        )

    # 5. Extract amount & create refund record
    amount = txn.get("amount", 0.0)
    refund_ref = generate_refund_reference()
    now = datetime.now(timezone.utc)
    reason = rec_doc.get("reason", "Gateway payment failed but bank amount was debited")

    refund_doc = {
        "transaction_id": payload.transaction_id,
        "refund_reference": refund_ref,
        "amount": amount,
        "status": RefundStatus.COMPLETED.value,
        "reason": reason,
        "created_at": now,
        "completed_at": now
    }

    # 6. Save in refunds collection
    try:
        refunds_col.insert_one(refund_doc)
    except DuplicateKeyError:
        refund_ref = generate_refund_reference()
        refund_doc["refund_reference"] = refund_ref
        refunds_col.insert_one(refund_doc)
    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while saving refund record: {str(err)}"
        )

    # 7. Update the main transaction lifecycle status.
    try:
        transactions_col.update_one(
            {"transaction_id": payload.transaction_id},
            {
                "$set": {
                    "status": "RESOLVED",
                    "updated_at": now,
                }
            },
        )
    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Refund completed but transaction status could not be updated: {str(err)}"
        )

    return refund_doc
