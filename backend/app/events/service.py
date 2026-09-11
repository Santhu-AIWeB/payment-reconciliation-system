from datetime import datetime, timezone

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from backend.app.database import get_db
from backend.app.events.schemas import PaymentEvent


def get_events_collection():
    return get_db()["payment_events"]


def init_event_indexes() -> None:
    events_collection = get_events_collection()

    events_collection.create_index(
        "event_id",
        unique=True,
        name="unique_event_id",
    )

    events_collection.create_index(
        "transaction_id",
        name="transaction_id_index",
    )

    events_collection.create_index(
        "correlation_id",
        name="correlation_id_index",
    )

    events_collection.create_index(
        "status",
        name="status_index",
    )

    events_collection.create_index(
        "created_at",
        name="created_at_index",
    )


def publish_event(event: PaymentEvent) -> dict:
    events_collection = get_events_collection()

    event_document = event.model_dump()

    # Store enum values as strings in MongoDB.
    event_document["event_type"] = event.event_type.value
    event_document["status"] = event.status.value

    try:
        events_collection.insert_one(event_document)
    except DuplicateKeyError:
        raise ValueError(
            f"Event already exists: {event.event_id}"
        )

    return event_document

def claim_next_pending_event() -> dict | None:
    """
    Atomically claim the oldest pending event.

    Returns the claimed event document, or None when no pending
    event is available.
    """
    events_collection = get_events_collection()

    return events_collection.find_one_and_update(
        {"status": "PENDING"},
        {
            "$set": {
                "status": "PROCESSING",
            }
        },
        sort=[("created_at", 1)],
        return_document=ReturnDocument.AFTER,
    )

def mark_event_processing(event_id: str) -> bool:
    events_collection = get_events_collection()

    result = events_collection.update_one(
        {
            "event_id": event_id,
            "status": "PENDING",
        },
        {
            "$set": {
                "status": "PROCESSING",
            }
        },
    )

    return result.modified_count == 1


def mark_event_completed(event_id: str) -> bool:
    events_collection = get_events_collection()

    result = events_collection.update_one(
        {"event_id": event_id},
        {
            "$set": {
                "status": "COMPLETED",
                "processed_at": datetime.now(timezone.utc),
            }
        },
    )

    return result.modified_count == 1


def mark_event_failed(
    event_id: str,
    error_message: str,
) -> bool:
    events_collection = get_events_collection()

    result = events_collection.update_one(
        {"event_id": event_id},
        {
            "$set": {
                "status": "FAILED",
                "error_message": error_message,
                "processed_at": datetime.now(timezone.utc),
            },
            "$inc": {
                "retry_count": 1,
            },
        },
    )

    return result.modified_count == 1
