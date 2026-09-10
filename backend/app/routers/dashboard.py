from fastapi import APIRouter, HTTPException, Depends, status
from pymongo.errors import PyMongoError

from backend.app.database import (
    get_transactions_collection,
    get_gateway_transactions_collection,
    get_bank_transactions_collection,
    get_reconciliations_collection,
    get_refunds_collection,
    get_retry_attempts_collection,
)

router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"]
)


# ---------------------------------------------------------------------------
# GET /api/dashboard/summary
# ---------------------------------------------------------------------------

@router.get("/summary")
def get_dashboard_summary(
    transactions_col=Depends(get_transactions_collection),
    reconciliations_col=Depends(get_reconciliations_collection),
    refunds_col=Depends(get_refunds_collection),
    retry_col=Depends(get_retry_attempts_collection),
):
    """
    Aggregate summary statistics for the admin dashboard.
    Returns counts of transactions, reconciliation outcomes,
    refunds, and retry attempts.
    """
    try:
        total_transactions = transactions_col.count_documents({})
        matched = reconciliations_col.count_documents({"reconciliation_status": "MATCHED"})
        mismatch = reconciliations_col.count_documents({"reconciliation_status": "MISMATCH"})
        pending_rec = reconciliations_col.count_documents({"reconciliation_status": "PENDING"})
        duplicate_rec = reconciliations_col.count_documents({"reconciliation_status": "DUPLICATE"})

        total_refunds = refunds_col.count_documents({})
        refunds_completed = refunds_col.count_documents({"status": "COMPLETED"})
        refunds_failed = refunds_col.count_documents({"status": "FAILED"})

        total_retry_attempts = retry_col.count_documents({})
        retry_success = retry_col.count_documents({"status": "SUCCESS"})
        retry_max_reached = retry_col.count_documents({"status": "MAX_ATTEMPTS_REACHED"})

        # Action required breakdown
        action_refund = reconciliations_col.count_documents({"action_required": "REFUND"})
        action_retry = reconciliations_col.count_documents({"action_required": "RETRY"})
        action_investigate = reconciliations_col.count_documents({"action_required": "INVESTIGATE"})
        action_wait = reconciliations_col.count_documents({"action_required": "WAIT"})

    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while computing summary: {str(err)}"
        )

    return {
        "transactions": {
            "total": total_transactions,
        },
        "reconciliations": {
            "matched": matched,
            "mismatch": mismatch,
            "pending": pending_rec,
            "duplicate": duplicate_rec,
        },
        "actions_required": {
            "refund": action_refund,
            "retry": action_retry,
            "investigate": action_investigate,
            "wait": action_wait,
        },
        "refunds": {
            "total": total_refunds,
            "completed": refunds_completed,
            "failed": refunds_failed,
        },
        "retries": {
            "total_attempts": total_retry_attempts,
            "success": retry_success,
            "max_attempts_reached": retry_max_reached,
        },
    }


# ---------------------------------------------------------------------------
# GET /api/dashboard/transactions
# ---------------------------------------------------------------------------

@router.get("/transactions")
def get_dashboard_transactions(
    transactions_col=Depends(get_transactions_collection),
    gateway_col=Depends(get_gateway_transactions_collection),
    bank_col=Depends(get_bank_transactions_collection),
    reconciliations_col=Depends(get_reconciliations_collection),
    refunds_col=Depends(get_refunds_collection),
    retry_col=Depends(get_retry_attempts_collection),
):
    """
    Returns all transactions enriched with their gateway, bank,
    reconciliation, refund, and retry information from a single call.
    Results are sorted by created_at descending (newest first).
    """
    try:
        transactions = list(
            transactions_col.find({}, {"_id": 0}).sort("created_at", -1)
        )
    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while fetching transactions: {str(err)}"
        )

    enriched = []
    for txn in transactions:
        txn_id = txn["transaction_id"]
        try:
            gateway_doc = gateway_col.find_one({"transaction_id": txn_id}, {"_id": 0})
            bank_doc = bank_col.find_one({"transaction_id": txn_id}, {"_id": 0})
            rec_doc = reconciliations_col.find_one({"transaction_id": txn_id}, {"_id": 0})
            refund_doc = refunds_col.find_one({"transaction_id": txn_id}, {"_id": 0})
            retry_docs = list(
                retry_col.find({"transaction_id": txn_id}, {"_id": 0}).sort("attempt_number", 1)
            )
        except PyMongoError as err:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error while enriching transaction {txn_id}: {str(err)}"
            )

        enriched.append({
            "transaction_id": txn_id,
            "amount": txn.get("amount"),
            "currency": txn.get("currency"),
            "status": txn.get("status"),
            "created_at": txn.get("created_at"),
            "updated_at": txn.get("updated_at"),
            "gateway": {
                "status": gateway_doc.get("status") if gateway_doc else None,
                "gateway_reference": gateway_doc.get("gateway_reference") if gateway_doc else None,
                "response_message": gateway_doc.get("response_message") if gateway_doc else None,
                "created_at": gateway_doc.get("created_at") if gateway_doc else None,
            } if gateway_doc else None,
            "bank": {
                "status": bank_doc.get("status") if bank_doc else None,
                "bank_reference": bank_doc.get("bank_reference") if bank_doc else None,
                "response_message": bank_doc.get("response_message") if bank_doc else None,
                "created_at": bank_doc.get("created_at") if bank_doc else None,
            } if bank_doc else None,
            "reconciliation": {
                "reconciliation_status": rec_doc.get("reconciliation_status") if rec_doc else None,
                "action_required": rec_doc.get("action_required") if rec_doc else None,
                "reason": rec_doc.get("reason") if rec_doc else None,
                "created_at": rec_doc.get("created_at") if rec_doc else None,
                "resolved_at": rec_doc.get("resolved_at") if rec_doc else None,
            } if rec_doc else None,
            "refund": {
                "status": refund_doc.get("status") if refund_doc else None,
                "refund_reference": refund_doc.get("refund_reference") if refund_doc else None,
                "amount": refund_doc.get("amount") if refund_doc else None,
                "reason": refund_doc.get("reason") if refund_doc else None,
                "created_at": refund_doc.get("created_at") if refund_doc else None,
                "completed_at": refund_doc.get("completed_at") if refund_doc else None,
            } if refund_doc else None,
            "retries": [
                {
                    "attempt_number": r.get("attempt_number"),
                    "status": r.get("status"),
                    "retry_reference": r.get("retry_reference"),
                    "reason": r.get("reason"),
                    "created_at": r.get("created_at"),
                    "completed_at": r.get("completed_at"),
                }
                for r in retry_docs
            ],
        })

    return enriched


# ---------------------------------------------------------------------------
# GET /api/dashboard/transactions/{transaction_id}
# ---------------------------------------------------------------------------

@router.get("/transactions/{transaction_id}")
def get_dashboard_transaction_detail(
    transaction_id: str,
    transactions_col=Depends(get_transactions_collection),
    gateway_col=Depends(get_gateway_transactions_collection),
    bank_col=Depends(get_bank_transactions_collection),
    reconciliations_col=Depends(get_reconciliations_collection),
    refunds_col=Depends(get_refunds_collection),
    retry_col=Depends(get_retry_attempts_collection),
):
    """
    Returns the complete lifecycle detail for a single transaction:
    base record, gateway record, bank record, reconciliation record,
    refund record (if any), and all retry attempts (if any).
    """
    try:
        txn = transactions_col.find_one({"transaction_id": transaction_id}, {"_id": 0})
        if not txn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transaction '{transaction_id}' not found."
            )
    except HTTPException:
        raise
    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(err)}"
        )

    try:
        gateway_doc = gateway_col.find_one({"transaction_id": transaction_id}, {"_id": 0})
        bank_doc = bank_col.find_one({"transaction_id": transaction_id}, {"_id": 0})
        rec_doc = reconciliations_col.find_one({"transaction_id": transaction_id}, {"_id": 0})
        refund_doc = refunds_col.find_one({"transaction_id": transaction_id}, {"_id": 0})
        retry_docs = list(
            retry_col.find({"transaction_id": transaction_id}, {"_id": 0}).sort("attempt_number", 1)
        )
    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while fetching related records: {str(err)}"
        )

    return {
        "transaction": txn,
        "gateway": gateway_doc,
        "bank": bank_doc,
        "reconciliation": rec_doc,
        "refund": refund_doc,
        "retries": retry_docs,
    }
