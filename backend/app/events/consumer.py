from datetime import datetime, timezone

from backend.app.events.schemas import EventStatus, EventType, PaymentEvent
from backend.app.events.service import (
    get_events_collection,
    mark_event_completed,
    mark_event_failed,
    mark_event_processing,
)


SUPPORTED_EVENT_TYPES = {
    EventType.PAYMENT_CREATED,
    EventType.GATEWAY_PROCESSED,
    EventType.BANK_PROCESSED,
    EventType.RECONCILIATION_REQUIRED,
    EventType.REFUND_REQUIRED,
    EventType.RETRY_REQUIRED,
    EventType.INVESTIGATION_REQUIRED,
}


def get_next_pending_event():
    """Return the oldest pending event, or None when the queue is empty."""
    events_collection = get_events_collection()

    event_document = events_collection.find_one(
        {"status": EventStatus.PENDING.value},
        sort=[("created_at", 1)],
    )

    if not event_document:
        return None

    event_document.pop("_id", None)

    return PaymentEvent.model_validate(event_document)


def handle_event(event: PaymentEvent) -> None:
    """
    Handle one event without duplicating existing business workflows.

    Phase 2C initially provides event lifecycle processing only.
    Downstream business handlers will be introduced separately.
    """
    if event.event_type not in SUPPORTED_EVENT_TYPES:
        raise ValueError(
            f"Unsupported event type: {event.event_type.value}"
        )

    # Phase 2C foundation:
    # Validate that the event is structurally correct and supported.
    print(
        f"[EVENT] Processed {event.event_type.value} "
        f"for transaction {event.transaction_id}"
    )


def process_next_event() -> bool:
    """
    Process one pending event.

    Returns:
        True when an event was processed.
        False when no pending event exists.
    """
    event = get_next_pending_event()

    if event is None:
        return False

    if not mark_event_processing(event.event_id):
        return False

    try:
        handle_event(event)
        mark_event_completed(event.event_id)
        return True

    except Exception as exc:
        mark_event_failed(
            event.event_id,
            str(exc),
        )
        return True


def process_pending_events(max_events: int = 10) -> int:
    """
    Process up to max_events pending events.

    Returns:
        Number of events attempted.
    """
    if max_events < 1:
        raise ValueError("max_events must be at least 1")

    processed_count = 0

    while processed_count < max_events:
        processed = process_next_event()

        if not processed:
            break

        processed_count += 1

    return processed_count
