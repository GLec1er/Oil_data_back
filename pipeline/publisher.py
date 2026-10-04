"""Publish generator or scenario messages to Kafka, keyed by well_id."""
import time

from kafka import KafkaProducer

from pipeline import config


def publish(messages: list[tuple[str, bytes]]) -> int:
    producer = KafkaProducer(
        bootstrap_servers=config.KAFKA_BOOTSTRAP,
        acks="all",
        retries=5,
        key_serializer=str.encode,
    )
    for key, value in messages:
        producer.send(config.TOPIC, key=key, value=value)
    producer.flush()
    producer.close()
    return len(messages)


def wait_until(predicate, timeout: float, interval: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if predicate():
                return True
        except (FileNotFoundError, KeyError, OSError):
            pass
        time.sleep(interval)
    return False
