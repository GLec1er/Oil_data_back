from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from pipeline import schemas

NOW = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)


def write_bronze(directory: Path, messages: list[tuple[str, bytes]], start_offset: int,
                 name: str) -> int:
    """Write messages as one committed Bronze file; return the next free offset."""
    rows = [
        {
            "value": value,
            "topic": "telemetry.raw",
            "partition": 0,
            "offset": start_offset + index,
            "kafka_timestamp": NOW,
            "ingested_at": NOW,
        }
        for index, (_, value) in enumerate(messages)
    ]
    directory.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows, schema=schemas.BRONZE), directory / name)
    return start_offset + len(messages)
