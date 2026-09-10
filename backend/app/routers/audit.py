from datetime import datetime, timezone
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
    prefix="/api/audit",
    tags=["Audit Trail"],
)


def _as_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _add_event(events, event_type, title, description, timestamp, reference=None):
    if timestamp is None:
        return
    events.append(
        {
            "event_type": event_type,
            "title": title,
            "description": description,
            "timestamp": _as_utc(timestamp),
            "reference": reference,
        }
    )


@router.get("/{transaction_id}", status_code=status.HTTP_200_OK)
def get_transaction_audit(
    transaction_id: str,
    transactions_col=Depends(get_transactions_collection),
    gateway_col=Depends(get_gateway_transactions_collection),
    bank_col=Depends(get_bank_transactions_collection),
    reconciliations_col=Depends(get_reconciliations_collection),
    refunds_col=Depends(get_refunds_collection),
    retry_col=Depends(get_retry_attempts_collection),
):
    """
    Build a chronological audit timeline from the existing transaction
    lifecycle records. No payment data is moved or modified.
    """
    try:
        txn = transactions_col.find_one({"transaction_id": transaction_id}, {"_id": 0})
        if not txn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transaction with ID '{transaction_id}' not found.",
            )

        gateway = gateway_col.find_one(
            {"transaction_id": transaction_id},
            {"_id": 0},
        )
        bank = bank_col.find_one(
            {"transaction_id": transaction_id},
            {"_id": 0},
        )
        reconciliation = reconciliations_col.find_one(
            {"transaction_id": transaction_id},
            {"_id": 0},
        )
        refund = refunds_col.find_one(
            {"transaction_id": transaction_id},
            {"_id": 0},
        )
        retries = list(
            retry_col.find(
                {"transaction_id": transaction_id},
                {"_id": 0},
            ).sort("attempt_number", 1)
        )

        events = []

        _add_event(
            events,
            "TRANSACTION_CREATED",
            "Transaction created",
            f"Payment transaction created for {txn.get('amount')} {txn.get('currency')}.",
            txn.get("created_at"),
        )

        if gateway:
            _add_event(
                events,
                "GATEWAY_PROCESSED",
                "Gateway processed",
                f"Gateway status: {gateway.get('status')}. {gateway.get('response_message', '')}".strip(),
                gateway.get("created_at"),
                gateway.get("gateway_reference"),
            )

        if bank:
            _add_event(
                events,
                "BANK_PROCESSED",
                "Bank processed",
                f"Bank status: {bank.get('status')}. {bank.get('response_message', '')}".strip(),
                bank.get("created_at"),
                bank.get("bank_reference"),
            )

        if reconciliation:
            _add_event(
                events,
                "RECONCILIATED",
                "Reconciliation completed",
                f"{reconciliation.get('reconciliation_status')} — {reconciliation.get('reason', '')}".strip(),
                reconciliation.get("created_at"),
            )

        if refund:
            _add_event(
                events,
                "REFUND_PROCESSED",
                f"Refund {refund.get('status', 'processed').lower()}",
                refund.get("reason", "Refund workflow processed."),
                refund.get("completed_at") or refund.get("created_at"),
                refund.get("refund_reference"),
            )

        for retry in retries:
            status_text = retry.get("status", "UNKNOWN")
            _add_event(
                events,
                "RETRY_PROCESSED",
                f"Retry attempt #{retry.get('attempt_number')}",
                f"Retry status: {status_text}. {retry.get('reason', '')}".strip(),
                retry.get("completed_at") or retry.get("created_at"),
                retry.get("retry_reference"),
            )

        events.sort(key=lambda item: item["timestamp"])

        return events

    except HTTPException:
        raise
    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while building audit timeline: {str(err)}",
        )
