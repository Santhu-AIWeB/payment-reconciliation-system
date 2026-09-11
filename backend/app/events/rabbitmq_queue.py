import json
import os

import pika

from backend.app.events.queue import EventQueue
from backend.app.events.schemas import PaymentEvent
from backend.app.events.service import publish_event


class RabbitMQEventQueue(EventQueue):
    """
    RabbitMQ-backed implementation of the EventQueue interface.

    MongoDB remains the existing event persistence and audit store.
    RabbitMQ handles message delivery.
    """

    EXCHANGE_NAME = "payment_events"
    QUEUE_NAME = "payment_event_queue"
    ROUTING_KEY = "payment.event"

    DLX_NAME = "payment_events_dlx"
    DLQ_NAME = "payment_event_dead_letter"
    DLQ_ROUTING_KEY = "payment.event.dead"

    def __init__(self) -> None:
        self.host = os.getenv("RABBITMQ_HOST", "localhost")
        self.port = int(os.getenv("RABBITMQ_PORT", "5672"))
        self.username = os.getenv(
            "RABBITMQ_USER",
            "payment_user",
        )
        self.password = os.getenv(
            "RABBITMQ_PASSWORD",
            "payment_password",
        )

    def _connect(self):
        credentials = pika.PlainCredentials(
            self.username,
            self.password,
        )

        parameters = pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            credentials=credentials,
        )

        return pika.BlockingConnection(parameters)

    def _ensure_topology(self, channel) -> None:
        channel.exchange_declare(
            exchange=self.EXCHANGE_NAME,
            exchange_type="direct",
            durable=True,
        )

        channel.exchange_declare(
            exchange=self.DLX_NAME,
            exchange_type="direct",
            durable=True,
        )

        channel.queue_declare(
            queue=self.DLQ_NAME,
            durable=True,
        )

        channel.queue_bind(
            exchange=self.DLX_NAME,
            queue=self.DLQ_NAME,
            routing_key=self.DLQ_ROUTING_KEY,
        )

        channel.queue_declare(
            queue=self.QUEUE_NAME,
            durable=True,
            arguments={
                "x-dead-letter-exchange": self.DLX_NAME,
                "x-dead-letter-routing-key": self.DLQ_ROUTING_KEY,
            },
        )

        channel.queue_bind(
            exchange=self.EXCHANGE_NAME,
            queue=self.QUEUE_NAME,
            routing_key=self.ROUTING_KEY,
        )

    def publish(self, event: PaymentEvent) -> dict:
        connection = self._connect()

        try:
            channel = connection.channel()
            self._ensure_topology(channel)

            message = event.model_dump(mode="json")

            channel.basic_publish(
                exchange=self.EXCHANGE_NAME,
                routing_key=self.ROUTING_KEY,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type="application/json",
                ),
            )

            return message

        finally:
            connection.close()

    def claim(self) -> PaymentEvent | None:
        raise NotImplementedError(
            "RabbitMQ consumption is handled by RabbitMQWorker."
        )

    def claim_by_id(self, event_id: str) -> PaymentEvent | None:
        raise NotImplementedError(
            "RabbitMQ targeted claiming is handled by RabbitMQWorker."
        )

    def complete(self, event_id: str) -> bool:
        raise NotImplementedError(
            "RabbitMQ acknowledgement is handled by RabbitMQWorker."
        )

    def fail(
        self,
        event_id: str,
        error_message: str,
    ) -> bool:
        raise NotImplementedError(
            "RabbitMQ failure handling is handled by RabbitMQWorker."
        )

    def retry(
        self,
        event_id: str,
        max_retries: int = 3,
    ) -> bool:
        raise NotImplementedError(
            "RabbitMQ retry handling is handled by RabbitMQWorker."
        )
