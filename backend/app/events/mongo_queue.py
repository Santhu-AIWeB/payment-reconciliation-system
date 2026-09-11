from pymongo import ReturnDocument

from backend.app.events.queue import EventQueue
from backend.app.events.schemas import PaymentEvent
from backend.app.events.service import (
    claim_next_pending_event,
    get_events_collection,
    mark_event_completed,
    mark_event_failed,
    publish_event,
    retry_failed_event,
)


class MongoEventQueue(EventQueue):
    """
    MongoDB-backed implementation of the EventQueue interface.

    This keeps the current event infrastructure working while
    allowing a real message broker to be introduced later.
    """

    def publish(self, event: PaymentEvent) -> dict:
        return publish_event(event)

    def claim(self) -> PaymentEvent | None:
        event_document = claim_next_pending_event()

        if not event_document:
            return None

        event_document.pop("_id", None)

        return PaymentEvent.model_validate(event_document)

    def claim_by_id(self, event_id: str) -> PaymentEvent | None:
        """
        Atomically claim one specific pending event by event ID.
        """

        events_collection = get_events_collection()

        event_document = events_collection.find_one_and_update(
            {
                "event_id": event_id,
                "status": "PENDING",
            },
            {
                "$set": {
                    "status": "PROCESSING",
                }
            },
            return_document=ReturnDocument.AFTER,
        )

        if not event_document:
            return None

        event_document.pop("_id", None)

        return PaymentEvent.model_validate(event_document)

    def complete(self, event_id: str) -> bool:
        return mark_event_completed(event_id)

    def fail(
        self,
        event_id: str,
        error_message: str,
    ) -> bool:
        return mark_event_failed(
            event_id,
            error_message,
        )

    def retry(
        self,
        event_id: str,
        max_retries: int = 3,
    ) -> bool:
        return retry_failed_event(
            event_id=event_id,
            max_retries=max_retries,
        )