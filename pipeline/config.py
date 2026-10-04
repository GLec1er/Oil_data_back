"""Runtime paths and Kafka settings, overridable through the environment."""
import os
from pathlib import Path

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
TOPIC = os.getenv("TELEMETRY_TOPIC", "telemetry.raw")
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
TRIGGER_SECONDS = int(os.getenv("TRIGGER_SECONDS", "10"))
SNAPSHOTS_TO_KEEP = int(os.getenv("SNAPSHOTS_TO_KEEP", "5"))

BRONZE_DIR = DATA_DIR / "bronze"
CHECKPOINT_DIR = DATA_DIR / "checkpoints"
MARTS_DIR = DATA_DIR / "marts"
