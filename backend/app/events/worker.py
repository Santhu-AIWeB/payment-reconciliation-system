import time

from backend.app.events.rabbitmq_worker import RabbitMQWorker


def main() -> None:
    """
    Run the RabbitMQ worker continuously.

    The worker keeps consuming payment events from RabbitMQ.
    If RabbitMQ temporarily becomes unavailable, the worker waits
    and tries again instead of exiting.
    """
    worker = RabbitMQWorker()

    print("[WORKER] RabbitMQ worker started")

    while True:
        try:
            processed = worker.consume_one()

            if not processed:
                time.sleep(1)

        except KeyboardInterrupt:
            print("[WORKER] Shutdown requested")
            break

        except Exception as exc:
            print(f"[WORKER] Connection/processing error: {exc}")
            time.sleep(3)


if __name__ == "__main__":
    main()