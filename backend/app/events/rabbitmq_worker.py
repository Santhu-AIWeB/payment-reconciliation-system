import json
import os
import requests
import pika

from backend.app.events.rabbitmq_queue import RabbitMQEventQueue
from backend.app.events.schemas import EventType, PaymentEvent
from backend.app.events.service import (
    mark_event_completed,
    mark_event_failed,
)


BACKEND_URL = os.getenv(
    "BACKEND_URL",
    "http://backend:8000",
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


class RabbitMQWorker:
    """
    RabbitMQ consumer worker.

    Messages are validated and acknowledged after successful
    business processing.

    Workflow:

        BANK_PROCESSED
            ↓
        Reconciliation
            ↓
        RECONCILIATION_REQUIRED
            ↓
        REFUND / RETRY / INVESTIGATE / WAIT / NONE

    Failed messages are retried up to MAX_RETRIES.
    After the retry limit is reached, the message is sent
    to the RabbitMQ dead-letter queue.
    """

    MAX_RETRIES = 3
    RETRY_HEADER = "x-retry-count"

    def __init__(self) -> None:
        self.queue = RabbitMQEventQueue()

    def _connect(self):
        return self.queue._connect()

    def _setup(self, channel) -> None:
        self.queue._ensure_topology(channel)

        channel.basic_qos(
            prefetch_count=1,
        )

    def process_message(self, body: bytes) -> PaymentEvent:
        """
        Deserialize and validate a RabbitMQ message.
        """

        payload = json.loads(body)

        event = PaymentEvent.model_validate(payload)

        if event.event_type not in SUPPORTED_EVENT_TYPES:
            raise ValueError(
                f"Unsupported event type: {event.event_type.value}"
            )

        print(
            f"[RABBITMQ] Processing {event.event_type.value} "
            f"for transaction {event.transaction_id}",
            flush=True,
        )

        return event

    def _get_retry_count(self, properties) -> int:
        """
        Read the RabbitMQ retry counter from message headers.
        """

        headers = properties.headers or {}

        retry_count = headers.get(
            self.RETRY_HEADER,
            0,
        )

        if not isinstance(retry_count, int):
            return 0

        return retry_count

    def _requeue_message(
        self,
        channel,
        method,
        properties,
        body,
        retry_count: int,
    ) -> None:
        """
        Publish the failed message back to the main exchange
        with an incremented retry counter, then ACK the original.
        """

        new_retry_count = retry_count + 1

        headers = dict(properties.headers or {})
        headers[self.RETRY_HEADER] = new_retry_count

        channel.basic_publish(
            exchange=self.queue.EXCHANGE_NAME,
            routing_key=self.queue.ROUTING_KEY,
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type=(
                    properties.content_type
                    or "application/json"
                ),
                headers=headers,
            ),
        )

        channel.basic_ack(
            delivery_tag=method.delivery_tag,
        )

        print(
            f"[RABBITMQ] RETRY "
            f"{new_retry_count}/{self.MAX_RETRIES}",
            flush=True,
        )

    def _process_business_event(
        self,
        event: PaymentEvent,
    ) -> None:
        """
        Execute the business workflow represented by an event.

        BANK_PROCESSED:
            Trigger reconciliation.

        RECONCILIATION_REQUIRED:
            Trigger the workflow requested by action_required.
        """

        transaction_id = event.transaction_id

        # =====================================================
        # BANK_PROCESSED -> RECONCILIATION
        # =====================================================

        if event.event_type == EventType.BANK_PROCESSED:

            print(
                "[RABBITMQ] BANK_PROCESSED received. "
                "Triggering reconciliation...",
                flush=True,
            )

            response = requests.post(
                f"{BACKEND_URL}/api/reconciliation/process",
                json={
                    "transaction_id": transaction_id,
                },
                timeout=10,
            )

            if not response.ok:
                raise RuntimeError(
                    "Reconciliation request failed: "
                    f"HTTP {response.status_code} - {response.text}"
                )

            print(
                "[RABBITMQ] Reconciliation request completed "
                f"for {transaction_id}",
                flush=True,
            )

            return

        # =====================================================
        # RECONCILIATION_REQUIRED -> NEXT ACTION
        # =====================================================

        if event.event_type == EventType.RECONCILIATION_REQUIRED:

            action_required = event.payload.get(
                "action_required"
            )

            print(
                "[RABBITMQ] RECONCILIATION_REQUIRED received "
                f"for {transaction_id}. "
                f"Action={action_required}",
                flush=True,
            )

            # -------------------------------------------------
            # REFUND
            # -------------------------------------------------

            if action_required == "REFUND":

                print(
                    f"[RABBITMQ] Triggering refund for "
                    f"{transaction_id}",
                    flush=True,
                )

                response = requests.post(
                    f"{BACKEND_URL}/api/refunds/process",
                    json={
                        "transaction_id": transaction_id,
                    },
                    timeout=10,
                )

                if not response.ok:
                    raise RuntimeError(
                        "Refund request failed: "
                        f"HTTP {response.status_code} - {response.text}"
                    )

                print(
                    f"[RABBITMQ] Refund completed for "
                    f"{transaction_id}",
                    flush=True,
                )

                return

            # -------------------------------------------------
            # RETRY
            # -------------------------------------------------

            if action_required == "RETRY":

                print(
                    f"[RABBITMQ] Triggering retry for "
                    f"{transaction_id}",
                    flush=True,
                )

                response = requests.post(
                    f"{BACKEND_URL}/api/retry/process",
                    json={
                        "transaction_id": transaction_id,
                    },
                    timeout=10,
                )

                if not response.ok:
                    raise RuntimeError(
                        "Retry request failed: "
                        f"HTTP {response.status_code} - {response.text}"
                    )

                print(
                    f"[RABBITMQ] Retry completed for "
                    f"{transaction_id}",
                    flush=True,
                )

                return

            # -------------------------------------------------
            # INVESTIGATE
            # -------------------------------------------------

            if action_required == "INVESTIGATE":

                print(
                    f"[RABBITMQ] Investigation required for "
                    f"{transaction_id}. "
                    "Leaving transaction for manual review.",
                    flush=True,
                )

                return

            # -------------------------------------------------
            # NONE / WAIT / OTHER
            # -------------------------------------------------

            print(
                "[RABBITMQ] No automatic workflow required "
                f"for {transaction_id}. "
                f"Action={action_required}",
                flush=True,
            )

            return

    def consume_one(self) -> bool:
        """
        Consume one message from RabbitMQ.

        Successful messages:
            - execute business workflow
            - update MongoDB event state to COMPLETED
            - ACK RabbitMQ message

        Failed messages:
            - update MongoDB event state to FAILED
            - retry through RabbitMQ until MAX_RETRIES
            - then send to the DLQ
        """

        connection = self._connect()

        try:
            channel = connection.channel()

            self._setup(channel)

            method, properties, body = channel.basic_get(
                queue=RabbitMQEventQueue.QUEUE_NAME,
                auto_ack=False,
            )

            if method is None:
                return False

            retry_count = self._get_retry_count(
                properties,
            )

            try:
                event = self.process_message(body)

                # Execute actual business workflow first.
                self._process_business_event(event)

                # Mark event completed only after successful
                # business processing.
                mark_event_completed(
                    event.event_id,
                )

                channel.basic_ack(
                    delivery_tag=method.delivery_tag,
                )

                print(
                    f"[RABBITMQ] ACK "
                    f"event={event.event_id}",
                    flush=True,
                )

                return True

            except Exception as exc:

                print(
                    f"[RABBITMQ] Processing failed: {exc}",
                    flush=True,
                )

                # Try to identify the event so MongoDB can
                # record the processing failure.
                try:
                    payload = json.loads(body)

                    event = PaymentEvent.model_validate(
                        payload
                    )

                    mark_event_failed(
                        event.event_id,
                        str(exc),
                    )

                except Exception as mongo_exc:

                    print(
                        "[RABBITMQ] Could not update "
                        "MongoDB failure state: "
                        f"{mongo_exc}",
                        flush=True,
                    )

                if retry_count < self.MAX_RETRIES:

                    self._requeue_message(
                        channel,
                        method,
                        properties,
                        body,
                        retry_count,
                    )

                else:

                    channel.basic_nack(
                        delivery_tag=method.delivery_tag,
                        requeue=False,
                    )

                    print(
                        "[RABBITMQ] MAX RETRIES REACHED "
                        "-> DLQ",
                        flush=True,
                    )

                return True

        finally:
            connection.close()