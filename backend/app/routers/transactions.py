import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException, Depends, status
from pymongo.errors import PyMongoError, DuplicateKeyError

from backend.app.schemas import (
    TransactionCreate,
    TransactionResponse,
    TransactionStatus,
)
from backend.app.database import (
    get_transactions_collection,
    get_db,
)

from backend.app.events.schemas import EventType, PaymentEvent
from backend.app.events.publisher import DualWriteEventPublisher


router = APIRouter(
    prefix="/api/transactions",
    tags=["Transactions"]
)


def generate_transaction_id() -> str:
    """Generate a unique human-readable transaction ID (e.g. TXN-A1B2C3D4E5F6)."""
    return f"TXN-{uuid.uuid4().hex[:12].upper()}"


@router.post(
    "",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_transaction(
    payload: TransactionCreate,
    collection=Depends(get_transactions_collection),
):
    """
    Create a new payment transaction record.

    - Generates unique transaction ID
    - Sets initial status to CREATED
    - Saves document to MongoDB
    - Publishes PAYMENT_CREATED event to RabbitMQ
    """
    txn_id = generate_transaction_id()
    now = datetime.now(timezone.utc)

    doc = {
        "transaction_id": txn_id,
        "amount": round(payload.amount, 2),
        "currency": payload.currency.upper(),
        "status": TransactionStatus.CREATED.value,
        "created_at": now,
        "updated_at": now,
    }

    try:
        collection.insert_one(doc)

    except DuplicateKeyError:
        txn_id = generate_transaction_id()
        doc["transaction_id"] = txn_id
        collection.insert_one(doc)

    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while saving transaction: {str(err)}",
        )

    # Publish PAYMENT_CREATED event after successful transaction creation.
    event = PaymentEvent(
        event_id=f"EVT-{uuid.uuid4().hex[:12].upper()}",
        event_type=EventType.PAYMENT_CREATED,
        transaction_id=txn_id,
        payload={
            "amount": doc["amount"],
            "currency": doc["currency"],
        },
        correlation_id=txn_id,
    )

    try:
        DualWriteEventPublisher().publish(event)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transaction created, but event publishing failed: {str(err)}",
        )

    return doc


@router.get("", response_model=List[TransactionResponse])
def get_all_transactions(
    collection=Depends(get_transactions_collection),
):
    """
    Retrieve all payment transactions.
    """
    try:
        cursor = collection.find({}, {"_id": 0})
        return list(cursor)

    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while retrieving transactions: {str(err)}",
        )


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction_by_id(
    transaction_id: str,
    collection=Depends(get_transactions_collection),
):
    """
    Retrieve a single transaction by its transaction_id.
    """
    try:
        doc = collection.find_one(
            {"transaction_id": transaction_id},
            {"_id": 0},
        )

        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transaction with ID '{transaction_id}' not found.",
            )

        return doc

    except HTTPException:
        raise

    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while retrieving transaction: {str(err)}",
        )


@router.delete("/{transaction_id}")
def delete_transaction(
    transaction_id: str,
    collection=Depends(get_transactions_collection),
):
    """
    Delete a transaction and all related records belonging to it.

    Related records removed:
    - gateway_transactions
    - bank_transactions
    - reconciliations
    - refunds
    - retry_attempts
    - payment_links
    - payment_events
    """
    db = get_db()

    # Make sure the transaction exists first.
    transaction = collection.find_one(
        {"transaction_id": transaction_id}
    )

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{transaction_id}' not found.",
        )

    try:
        collections_to_clean = [
            "gateway_transactions",
            "bank_transactions",
            "reconciliations",
            "refunds",
            "retry_attempts",
            "payment_links",
            "payment_events",
        ]

        deleted_counts = {}

        for collection_name in collections_to_clean:
            result = db[collection_name].delete_many(
                {"transaction_id": transaction_id}
            )
            deleted_counts[collection_name] = result.deleted_count

        # Delete the main transaction last.
        transaction_result = collection.delete_one(
            {"transaction_id": transaction_id}
        )

        deleted_counts["transactions"] = transaction_result.deleted_count

        return {
            "success": True,
            "transaction_id": transaction_id,
            "message": "Transaction and related records deleted successfully.",
            "deleted_counts": deleted_counts,
        }

    except PyMongoError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while deleting transaction: {str(err)}",
        )