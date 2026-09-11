from backend.app.events.mongo_queue import MongoEventQueue
from backend.app.events.schemas import EventType, PaymentEvent


SUPPORTED_EVENT_TYPES = {
    EventType.PAYMENT_CREATED,
    EventType.GATEWAY_PROCESSED,
    EventType.BANK_PROCESSED,
    EventType.RECONCILIATION_REQUIRED,
    EventType.REFUND_REQUIRED,
    EventType.RETRY_REQUIRED,
    EventType.INVESTIGATION_REQUIRED,
}


event_queue = MongoEventQueue()


def get_next_pending_event() -> PaymentEvent | None:
    """
    Claim and return the next eligible event through the queue abstraction.
    """
    return event_queue.claim()


def handle_event(event: PaymentEvent) -> None:
    """
    Handle one event without duplicating existing business workflows.

    Phase 2F keeps the existing event-processing behavior while
    routing queue operations through the EventQueue abstraction.
    """
    if event.event_type not in SUPPORTED_EVENT_TYPES:
        raise ValueError(
            f"Unsupported event type: {event.event_type.value}"
        )

    print(
        f"[EVENT] Processed {event.event_type.value} "
        f"for transaction {event.transaction_id}"
    )


def process_next_event() -> bool:
    """
    Process one pending event.

    The queue implementation atomically claims the event before processing.
    """
    event = get_next_pending_event()

    if event is None:
        return False

    try:
        handle_event(event)
        event_queue.complete(event.event_id)
        return True

    except Exception as exc:
        event_queue.fail(
            event.event_id,
            str(exc),
        )
        return True


def retry_event(
    event_id: str,
    max_retries: int = 3,
) -> bool:
    """
    Re-queue a failed event through the queue abstraction.
    """
    return event_queue.retry(
        event_id=event_id,
        max_retries=max_retries,
    )


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