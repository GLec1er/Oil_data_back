"""Pure Bronze -> Silver / rejects / conflicts / marts transformation."""
import math
from collections import defaultdict
from datetime import datetime
from typing import Any, Iterable

import pyarrow as pa

from pipeline import schemas
from pipeline.contract import Rejection, measurement_key, parse_message


def _coordinates(row: dict[str, Any]) -> tuple:
    return (row["topic"], row["partition"], row["offset"])


def build_datasets(bronze_rows: Iterable[dict[str, Any]]) -> dict[str, pa.Table]:
    groups: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
    rejects: list[dict] = []
    seen: set[tuple] = set()

    for row in sorted(bronze_rows, key=_coordinates):
        if _coordinates(row) in seen:
            continue
        seen.add(_coordinates(row))
        result = parse_message(row["value"])
        if isinstance(result, Rejection):
            rejects.append(
                {
                    "reason": result.reason,
                    "raw": row["value"],
                    "topic": row["topic"],
                    "kafka_partition": row["partition"],
                    "kafka_offset": row["offset"],
                }
            )
        else:
            groups[result["event_id"]].append((result, row))

    silver: list[dict] = []
    conflicts: list[dict] = []
    for event_id in sorted(groups):
        items = groups[event_id]
        if len({measurement_key(event) for event, _ in items}) > 1:
            conflicts.extend(
                {
                    "event_id": event_id,
                    "raw": row["value"],
                    "topic": row["topic"],
                    "kafka_partition": row["partition"],
                    "kafka_offset": row["offset"],
                }
                for _, row in items
            )
            continue
        event, row = min(
            items, key=lambda item: (item[0]["emitted_at"], *_coordinates(item[1])[1:])
        )
        silver.append(
            {**event, "kafka_partition": row["partition"], "kafka_offset": row["offset"]}
        )

    hourly = _aggregate(silver, "hour_start", _floor_hour)
    daily = _aggregate(silver, "day_start", _floor_day)
    return {
        "silver": pa.Table.from_pylist(silver, schema=schemas.SILVER),
        "rejects": pa.Table.from_pylist(rejects, schema=schemas.REJECTS),
        "conflicts": pa.Table.from_pylist(conflicts, schema=schemas.CONFLICTS),
        "hourly": pa.Table.from_pylist(hourly, schema=schemas.HOURLY),
        "daily": pa.Table.from_pylist(daily, schema=schemas.DAILY),
    }


def _floor_hour(moment: datetime) -> datetime:
    return moment.replace(minute=0, second=0, microsecond=0)


def _floor_day(moment: datetime) -> datetime:
    return moment.replace(hour=0, minute=0, second=0, microsecond=0)


def _aggregate(silver: list[dict], period_field: str, floor) -> list[dict]:
    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for event in silver:
        buckets[(floor(event["event_time"]), event["well_id"])].append(event)
    rows = []
    for (period, well_id), events in sorted(buckets.items()):
        count = len(events)
        rows.append(
            {
                period_field: period,
                "well_id": well_id,
                "readings": count,
                "avg_pressure_bar": math.fsum(e["pressure_bar"] for e in events) / count,
                "avg_temperature_c": math.fsum(e["temperature_c"] for e in events)
                / count,
                "avg_flow_m3_h": math.fsum(e["flow_m3_h"] for e in events) / count,
                "max_water_cut_pct": max(e["water_cut_pct"] for e in events),
            }
        )
    return rows


