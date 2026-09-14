from backend.app.events.rabbitmq_queue import RabbitMQEventQueue
from backend.app.events.schemas import PaymentEvent
from backend.app.events.service import (
    get_event,
    mark_event_broker_error,
    mark_event_broker_published,
    persist_event,
)


class DualWriteEventPublisher:
    """
    Persist a payment event in MongoDB and publish the same event to RabbitMQ.

    MongoDB is the durable event history. RabbitMQ is the delivery mechanism.
    These two systems cannot be made truly atomic with a simple dual write,
    so the MongoDB record remains available for recovery if broker delivery
    is temporarily unavailable.
    """

    def __init__(self) -> None:
        self.queue = RabbitMQEventQueue()

    def publish(self, event: PaymentEvent) -> dict:
        existing = get_event(event.event_id)

        if existing is None:
            event_document = persist_event(event)
        else:
            event_document = existing

        # Idempotent delivery: a retry of the API call does not create a
        # second RabbitMQ message once the original publication succeeded.
        if event_document.get("broker_published_at") is None:
            try:
                self.queue.publish(event)
                mark_event_broker_published(event.event_id)
            except Exception as exc:
                mark_event_broker_error(event.event_id, str(exc))
                raise

        return event_document
