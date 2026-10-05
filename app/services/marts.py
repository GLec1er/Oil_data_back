"""Read-only access to the published marts through the active.json manifest.

Independent of the pipeline package on purpose: the API only needs Parquet and
the manifest contract, so it can be deployed without Spark.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

PERIOD_COLUMN = {"hourly": "hour_start", "daily": "day_start"}


class SnapshotUnavailable(Exception):
    """No complete snapshot has been published yet."""


def _read_once(marts_dir: Path, name: str) -> tuple[dict[str, Any], pa.Table]:
    try:
        manifest = json.loads((marts_dir / "active.json").read_text())
    except FileNotFoundError as error:
        raise SnapshotUnavailable("no snapshot published yet") from error
    table = pq.read_table(marts_dir / manifest["path"] / f"{name}.parquet")
    return manifest, table


def read_table(marts_dir: Path, name: str) -> tuple[dict[str, Any], pa.Table]:
    """Read one dataset of the active snapshot.

    Retries once: a publish may replace active.json and prune the snapshot
    this call resolved between reading the manifest and opening the files.
    """
    try:
        return _read_once(marts_dir, name)
    except FileNotFoundError:
        try:
            return _read_once(marts_dir, name)
        except FileNotFoundError as error:
            raise SnapshotUnavailable("snapshot files are not readable") from error


def _utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment


def query_mart(
    marts_dir: Path,
    granularity: str,
    *,
    well_id: str | None,
    start: datetime | None,
    end: datetime | None,
    limit: int,
    offset: int,
) -> tuple[dict[str, Any], int, list[dict[str, Any]]]:
    manifest, table = read_table(marts_dir, granularity)
    period = PERIOD_COLUMN[granularity]
    period_type = table[period].type
    mask = pa.array([True] * table.num_rows)
    if well_id is not None:
        mask = pc.and_(mask, pc.equal(table["well_id"], well_id))
    if start is not None:
        lower = pa.scalar(_utc(start), period_type)
        mask = pc.and_(mask, pc.greater_equal(table[period], lower))
    if end is not None:
        upper = pa.scalar(_utc(end), period_type)
        mask = pc.and_(mask, pc.less(table[period], upper))
    table = table.filter(mask).sort_by([(period, "ascending"), ("well_id", "ascending")])
    total = table.num_rows
    rows = table.slice(offset, limit).to_pylist()
    for row in rows:
        row["period_start"] = row.pop(period)
    return manifest, total, rows


def list_wells(marts_dir: Path) -> tuple[dict[str, Any], list[str]]:
    manifest, table = read_table(marts_dir, "daily")
    return manifest, sorted(set(table["well_id"].to_pylist()))
