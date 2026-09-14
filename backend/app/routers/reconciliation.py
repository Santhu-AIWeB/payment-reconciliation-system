import uuid
from datetime import datetime, timezone

from backend.app.events.schemas import EventType, PaymentEvent
from backend.app.events.publisher import DualWriteEventPublisher

from fastapi import APIRouter, HTTPException, Depends, status
from pymongo.errors import PyMongoError, DuplicateKeyError

from backend.app.schemas import (
    ReconciliationRequest,
    ReconciliationResponse,
    ReconciliationStatus,
    ActionRequired,
)
from backend.app.database import (
    get_transactions_collection,
    get_gateway_transactions_collection,
    get_bank_transactions_collection,
    get_reconciliations_collection,
)

router = APIRouter(
    prefix="/api/reconciliation",
    tags=["Reconciliation Engine"],
)


@router.post(
    "/process",
    response_model=ReconciliationResponse,
    status_code=status.HTTP_200_OK,
)
def process_reconciliation(
    payload: ReconciliationRequest,
    transactions_col=Depends(get_transactions_collection),
    gateway_col=Depends(get_gateway_transactions_collection),
    bank_col=Depends(get_bank_transactions_collection),
    reconciliations_col=Depends(get_reconciliations_collection),
):
    """Process reconciliation with duplicate-safe persistence."""

    # 1. Verify transaction exists
    try:
        txn = transactions_col.find_one(
            {"transaction_id": payload.transaction_id}
        )

        if not txn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transaction with ID '{payload.transaction_id}' not found.",
            )

    except HTTPException:
        raise

    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while querying transaction: {str(err)}",
        )

    # 2. Fast duplicate check
    try:
        existing_rec = reconciliations_col.find_one(
            {"transaction_id": payload.transaction_id},
            {"_id": 0},
        )

        if existing_rec:
            return {
                "transaction_id": payload.transaction_id,
                "gateway_status": existing_rec.get("gateway_status"),
                "bank_status": existing_rec.get("bank_status"),
                "reconciliation_status": ReconciliationStatus.DUPLICATE.value,
                "reason": "Transaction has already been reconciled",
                "action_required": ActionRequired.BLOCK.value,
                "created_at": existing_rec.get("created_at"),
                "resolved_at": existing_rec.get("resolved_at"),
            }

    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while checking existing reconciliation: {str(err)}",
        )

    # 3. Retrieve gateway and bank records
    try:
        gateway_doc = gateway_col.find_one(
            {"transaction_id": payload.transaction_id}
        )
        bank_doc = bank_col.find_one(
            {"transaction_id": payload.transaction_id}
        )

    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while fetching gateway/bank records: {str(err)}",
        )

    gateway_status = gateway_doc.get("status") if gateway_doc else None
    bank_status = bank_doc.get("status") if bank_doc else None

    now = datetime.now(timezone.utc)

    # 4. Evaluate reconciliation rules
    if not gateway_doc or not bank_doc:
        rec_status = ReconciliationStatus.PENDING.value
        action = ActionRequired.WAIT.value
        reason = (
            "Gateway or bank transaction record is not yet available"
        )

    elif gateway_status == "SUCCESS" and bank_status == "DEBITED":
        rec_status = ReconciliationStatus.MATCHED.value
        action = ActionRequired.NONE.value
        reason = (
            "Gateway payment successful and bank amount debited"
        )

    elif gateway_status == "FAILED" and bank_status == "DEBITED":
        rec_status = ReconciliationStatus.MISMATCH.value
        action = ActionRequired.REFUND.value
        reason = (
            "Gateway payment failed but bank amount was debited"
        )

    elif gateway_status == "SUCCESS" and bank_status == "NOT_DEBITED":
        rec_status = ReconciliationStatus.MISMATCH.value
        action = ActionRequired.RETRY.value
        reason = (
            "Gateway payment successful but bank amount was not debited"
        )

    elif gateway_status == "TIMEOUT" and bank_status == "DEBITED":
        rec_status = ReconciliationStatus.MISMATCH.value
        action = ActionRequired.INVESTIGATE.value
        reason = (
            "Gateway timed out but bank amount was debited"
        )

    elif gateway_status == "TIMEOUT" and bank_status == "NOT_DEBITED":
        rec_status = ReconciliationStatus.PENDING.value
        action = ActionRequired.RETRY.value
        reason = (
            "Gateway timed out and bank amount was not debited"
        )

    elif gateway_status == "SUCCESS" and bank_status == "DELAYED":
        rec_status = ReconciliationStatus.PENDING.value
        action = ActionRequired.WAIT.value
        reason = (
            "Gateway payment succeeded but bank transaction is delayed"
        )

    else:
        rec_status = ReconciliationStatus.MISMATCH.value
        action = ActionRequired.INVESTIGATE.value
        reason = (
            "Unexpected gateway/bank status combination detected: "
            f"Gateway={gateway_status}, Bank={bank_status}"
        )

    rec_doc = {
        "transaction_id": payload.transaction_id,
        "gateway_status": gateway_status,
        "bank_status": bank_status,
        "reconciliation_status": rec_status,
        "reason": reason,
        "action_required": action,
        "created_at": now,
        "resolved_at": None,
    }

    # 5. Unique transaction_id index makes concurrent reconciliation calls safe.
    try:
        reconciliations_col.insert_one(rec_doc)

    except DuplicateKeyError:
        existing_rec = reconciliations_col.find_one(
            {"transaction_id": payload.transaction_id},
            {"_id": 0},
        )

        if existing_rec:
            return {
                "transaction_id": payload.transaction_id,
                "gateway_status": existing_rec.get("gateway_status"),
                "bank_status": existing_rec.get("bank_status"),
                "reconciliation_status": ReconciliationStatus.DUPLICATE.value,
                "reason": "Transaction has already been reconciled",
                "action_required": ActionRequired.BLOCK.value,
                "created_at": existing_rec.get("created_at"),
                "resolved_at": existing_rec.get("resolved_at"),
            }

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate reconciliation detected. Please retry the request.",
        )

    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while saving reconciliation result: {str(err)}",
        )

    # Phase 2B.4:
    # Publish RECONCILIATION_REQUIRED only after the
    # reconciliation result has been successfully persisted.
    event = PaymentEvent(
        event_id=f"EVT-{uuid.uuid4().hex[:12].upper()}",
        event_type=EventType.RECONCILIATION_REQUIRED,
        transaction_id=payload.transaction_id,
        payload={
            "gateway_status": rec_doc["gateway_status"],
            "bank_status": rec_doc["bank_status"],
            "reconciliation_status": rec_doc["reconciliation_status"],
            "action_required": rec_doc["action_required"],
            "reason": rec_doc["reason"],
        },
        correlation_id=payload.transaction_id,
    )

    DualWriteEventPublisher().publish(event)

    return rec_doc