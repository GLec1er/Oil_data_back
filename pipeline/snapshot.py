"""Versioned snapshots published through an atomically replaced active.json."""
import fcntl
import json
import os
import shutil
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import pyarrow as pa
import pyarrow.parquet as pq

from pipeline import schemas
from pipeline.bronze import read_bronze
from pipeline.config import SNAPSHOTS_TO_KEEP
from pipeline.transform import build_datasets

MANIFEST = "active.json"


class SnapshotError(RuntimeError):
    pass


@contextmanager
def exclusive(root: Path) -> Iterator[None]:
    """Serialize publishers. Replay holds this lock, which pauses the materializer."""
    root.mkdir(parents=True, exist_ok=True)
    with open(root / ".publish.lock", "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def read_tables(directory: Path) -> dict[str, pa.Table]:
    return {
        name: pq.read_table(directory / f"{name}.parquet", schema=schema)
        for name, schema in schemas.TABLE_SCHEMAS.items()
    }


def validate(directory: Path) -> dict[str, int]:
    tables = read_tables(directory)
    silver = tables["silver"]
    ids = silver.column("event_id").to_pylist()
    if len(ids) != len(set(ids)):
        raise SnapshotError("duplicate event_id in silver")
    for mart in ("hourly", "daily"):
        total = sum(tables[mart].column("readings").to_pylist())
        if total != silver.num_rows:
            raise SnapshotError(f"{mart} reading count {total} != silver {silver.num_rows}")
    return {name: table.num_rows for name, table in tables.items()}


def read_manifest(root: Path) -> dict | None:
    try:
        return json.loads((root / MANIFEST).read_text())
    except FileNotFoundError:
        return None


def _write_manifest(root: Path, manifest: dict) -> None:
    temporary = root / f".{MANIFEST}.tmp"
    temporary.write_text(json.dumps(manifest, indent=2))
    with open(temporary, "rb") as handle:
        os.fsync(handle.fileno())
    os.replace(temporary, root / MANIFEST)


def publish(root: Path, snapshot_id: str, tables: dict[str, pa.Table]) -> dict:
    """Write, validate and activate a snapshot. Caller must hold exclusive(root).

    Idempotent per snapshot_id: an already complete snapshot is re-activated
    instead of rewritten, so a retried foreachBatch is safe.
    """
    final = root / "snapshots" / snapshot_id
    if not final.is_dir():
        staging = root / "staging" / f"{snapshot_id}-{os.getpid()}"
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True)
        try:
            for name, table in tables.items():
                pq.write_table(table, staging / f"{name}.parquet")
            validate(staging)
            final.parent.mkdir(parents=True, exist_ok=True)
            os.rename(staging, final)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
    counts = validate(final)
    manifest = {
        "snapshot_id": snapshot_id,
        "path": f"snapshots/{snapshot_id}",
        "published_at": datetime.now(timezone.utc).isoformat(),
        "counts": counts,
    }
    _write_manifest(root, manifest)
    _prune(root, keep=snapshot_id)
    return manifest


def _prune(root: Path, keep: str) -> None:
    snapshots = sorted(
        (path for path in (root / "snapshots").iterdir() if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old in snapshots[SNAPSHOTS_TO_KEEP:]:
        if old.name != keep:
            shutil.rmtree(old, ignore_errors=True)


def materialize(bronze_dir: Path, root: Path, snapshot_id: str) -> dict:
    """Rebuild every dataset from all committed Bronze data and publish it."""
    with exclusive(root):
        return publish(root, snapshot_id, build_datasets(read_bronze(bronze_dir)))


def replay(bronze_dir: Path, root: Path) -> dict:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return materialize(bronze_dir, root, f"replay-{stamp}")


def read_active(root: Path) -> tuple[dict, dict[str, pa.Table]]:
    manifest = read_manifest(root)
    if manifest is None:
        raise SnapshotError("no active snapshot published yet")
    return manifest, read_tables(root / manifest["path"])
