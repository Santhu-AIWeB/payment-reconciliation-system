from backend.app.events.schemas import EventType, PaymentEvent

from backend.app.events.service import (
    claim_next_pending_event,
    mark_event_completed,
    mark_event_failed,
    retry_failed_event,
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
    """
    Atomically claim and return the oldest pending event.

    The event is moved from PENDING to PROCESSING as part
    of the same MongoDB operation.
    """
    event_document = claim_next_pending_event()

    if not event_document:
        return None

    event_document.pop("_id", None)

    return PaymentEvent.model_validate(event_document)


def handle_event(event: PaymentEvent) -> None:
    """
    Handle one event without duplicating existing business workflows.

    Phase 2D initially provides atomic event claiming and
    event lifecycle processing only.
    Downstream business handlers will be introduced separately.
    """
    if event.event_type not in SUPPORTED_EVENT_TYPES:
        raise ValueError(
            f"Unsupported event type: {event.event_type.value}"
        )

    # Phase 2D foundation:
    # Validate that the event is structurally correct and supported.
    print(
        f"[EVENT] Processed {event.event_type.value} "
        f"for transaction {event.transaction_id}"
    )


def process_next_event() -> bool:
    """
    Process one pending event.

    The event is atomically claimed before processing.

    Returns:
        True when an event was processed.
        False when no pending event exists.
    """
    event = get_next_pending_event()

    if event is None:
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


def retry_event(
    event_id: str,
    max_retries: int = 3,
) -> bool:
    """
    Re-queue a failed event when the retry limit allows it.

    Returns:
        True when the failed event was moved back to PENDING.
        False otherwise.
    """
    return retry_failed_event(
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
