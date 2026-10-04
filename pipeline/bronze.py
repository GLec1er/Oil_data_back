"""Read committed Bronze Parquet files written by the Spark file sink."""
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pyarrow.parquet as pq

from pipeline import schemas


def committed_files(bronze_dir: Path) -> list[Path]:
    """Files recorded in the sink's _spark_metadata log (all files if absent)."""
    metadata = bronze_dir / "_spark_metadata"
    if not metadata.is_dir():
        return sorted(
            path
            for path in bronze_dir.rglob("*.parquet")
            if not any(part.startswith(("_", ".")) for part in path.parts)
        )
    files: set[Path] = set()
    for log in sorted(metadata.iterdir()):
        if log.name.startswith(".") or log.suffix == ".crc":
            continue
        for line in log.read_text().splitlines()[1:]:
            entry = json.loads(line)
            path = Path(urlparse(entry["path"]).path)
            if entry.get("action", "add") == "delete":
                files.discard(path)
            elif not entry.get("isDir"):
                files.add(path)
    return sorted(path for path in files if path.exists())


def read_bronze(bronze_dir: Path) -> list[dict[str, Any]]:
    columns = schemas.BRONZE.names
    rows: list[dict[str, Any]] = []
    for path in committed_files(bronze_dir):
        rows.extend(pq.ParquetFile(path).read(columns=columns).to_pylist())
    return rows
