"""Fixed event sets for the stop/restart recovery demonstration."""
import json
from datetime import datetime, timedelta, timezone

from pipeline.generator import iso, make_event

SEED = 7
DAY = datetime(2026, 10, 1, tzinfo=timezone.utc)


def _at(hour: int, minute: int = 0) -> datetime:
    return DAY.replace(hour=hour, minute=minute)


def _pack(events: list[dict]) -> list[tuple[str, bytes]]:
    return [(event["well_id"], json.dumps(event).encode()) for event in events]


def baseline() -> list[tuple[str, bytes]]:
    return _pack(
        [
            make_event(SEED, "NORTH-07", _at(10, 0), pressure_bar=80.0),
            make_event(SEED, "NORTH-07", _at(10, 15), pressure_bar=100.0),
            make_event(SEED, "NORTH-07", _at(11, 0), pressure_bar=90.0),
            make_event(SEED, "EAST-12", _at(10, 0)),
        ]
    )


def outage() -> list[tuple[str, bytes]]:
    duplicate = make_event(
        SEED,
        "NORTH-07",
        _at(10, 0),
        pressure_bar=80.0,
        emitted_at=_at(10, 0) + timedelta(hours=3),
    )
    late_v2 = make_event(
        SEED,
        "NORTH-07",
        _at(10, 5),
        schema_version=2,
        pressure_bar=120.0,
        emitted_at=_at(10, 0) + timedelta(hours=3),
    )
    return _pack([duplicate, late_v2]) + [("NORTH-07", b"{this is not json")]


# Expected state after each phase (counts and the NORTH-07 10:00 hourly row).
EXPECTED = {
    "baseline": {"bronze": 4, "silver": 4, "rejects": 0, "conflicts": 0},
    "final": {
        "bronze": 7,
        "silver": 5,
        "rejects": 1,
        "conflicts": 0,
        "north_hour": {
            "hour_start": iso(_at(10)),
            "readings": 3,
            "avg_pressure_bar": 100.0,
        },
        "north_day_readings": 4,
        "pump_populated": 1,
    },
}
