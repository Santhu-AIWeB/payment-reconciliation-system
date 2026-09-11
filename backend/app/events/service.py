from datetime import datetime, timedelta, timezone

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

    events_collection.create_index(
        "next_retry_at",
        name="next_retry_at_index",
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
    Atomically claim the oldest pending event that is ready for processing.

    An event is eligible when:
    - it has no next_retry_at value, or
    - next_retry_at is null, or
    - next_retry_at is less than or equal to the current UTC time.

    Events that are waiting for a future retry time are skipped.
    """
    events_collection = get_events_collection()

    now = datetime.now(timezone.utc)

    return events_collection.find_one_and_update(
        {
            "status": "PENDING",
            "$or": [
                {"next_retry_at": {"$exists": False}},
                {"next_retry_at": None},
                {"next_retry_at": {"$lte": now}},
            ],
        },
        {
            "$set": {
                "status": "PROCESSING",
            }
        },
        sort=[
            ("next_retry_at", 1),
            ("created_at", 1),
        ],
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


def retry_failed_event(
    event_id: str,
    max_retries: int = 3,
) -> bool:
    """
    Move a failed event back to PENDING when the retry limit allows it.

    Uses exponential backoff:
        retry 1 -> 1 second
        retry 2 -> 2 seconds
        retry 3 -> 4 seconds

    Returns:
        True when the event was successfully re-queued.
        False when the event does not exist, is not FAILED,
        or has reached the retry limit.
    """
    if max_retries < 1:
        raise ValueError("max_retries must be at least 1")

    events_collection = get_events_collection()

    event = events_collection.find_one(
        {
            "event_id": event_id,
            "status": "FAILED",
        }
    )

    if not event:
        return False

    retry_count = event.get("retry_count", 0)

    if retry_count >= max_retries:
        return False

    delay_seconds = 2 ** (retry_count - 1) if retry_count > 0 else 1

    next_retry_at = datetime.now(timezone.utc) + timedelta(
        seconds=delay_seconds
    )

    result = events_collection.update_one(
        {
            "event_id": event_id,
            "status": "FAILED",
            "retry_count": {"$lt": max_retries},
        },
        {
            "$set": {
                "status": "PENDING",
                "error_message": None,
                "processed_at": None,
                "next_retry_at": next_retry_at,
            }
        },
    )

    return result.modified_count == 1