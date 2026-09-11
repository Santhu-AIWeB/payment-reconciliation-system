import json

from backend.app.events.rabbitmq_queue import RabbitMQEventQueue
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


class RabbitMQWorker:
    """
    RabbitMQ consumer worker.

    Messages are validated and acknowledged after successful
    processing. Failed messages are retried up to MAX_RETRIES,
    after which they are dead-lettered.
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
            f"for transaction {event.transaction_id}"
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
            properties=__import__("pika").BasicProperties(
                delivery_mode=2,
                content_type=properties.content_type
                or "application/json",
                headers=headers,
            ),
        )

        channel.basic_ack(
            delivery_tag=method.delivery_tag,
        )

        print(
            f"[RABBITMQ] RETRY {new_retry_count}/"
            f"{self.MAX_RETRIES}"
        )

    def consume_one(self) -> bool:
        """
        Consume one message from RabbitMQ.

        Successful messages are ACKed.

        Failed messages are republished with an incremented
        retry counter until MAX_RETRIES is reached.

        Once MAX_RETRIES is reached, the original message is
        rejected without requeue so RabbitMQ dead-letters it.
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
                self.process_message(body)

                channel.basic_ack(
                    delivery_tag=method.delivery_tag,
                )

                print("[RABBITMQ] ACK")

                return True

            except Exception as exc:
                print(
                    f"[RABBITMQ] Processing failed: {exc}"
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
                        "→ DLQ"
                    )

                return True

        finally:
            connection.close()