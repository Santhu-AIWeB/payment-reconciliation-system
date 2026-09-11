from abc import ABC, abstractmethod

from backend.app.events.schemas import PaymentEvent


class EventQueue(ABC):
    """
    Abstract interface for the payment event queue.

    The current implementation will continue using MongoDB.
    A real message broker can be plugged in later without
    changing the event consumer's business logic.
    """

    @abstractmethod
    def publish(self, event: PaymentEvent) -> dict:
        """Publish an event to the queue."""
        raise NotImplementedError

    @abstractmethod
    def claim(self) -> PaymentEvent | None:
        """Claim the next eligible event for processing."""
        raise NotImplementedError

    @abstractmethod
    def claim_by_id(self, event_id: str) -> PaymentEvent | None:
        """Atomically claim one specific event by ID."""
        raise NotImplementedError

    @abstractmethod
    def complete(self, event_id: str) -> bool:
        """Mark an event as successfully processed."""
        raise NotImplementedError

    @abstractmethod
    def fail(self, event_id: str, error_message: str) -> bool:
        """Mark an event as failed."""
        raise NotImplementedError

    @abstractmethod
    def retry(self, event_id: str, max_retries: int = 3) -> bool:
        """Re-queue a failed event."""
        raise NotImplementedError