"""Deterministic telemetry generator. Same inputs always give the same events."""
import hashlib
import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

SCENARIOS = ("normal", "duplicates", "late", "v2", "faults")
NAMESPACE = uuid.UUID("6f0f1d7e-3a52-4c2b-9f0a-0a1b2c3d4e5f")


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def event_id_for(seed: int, well_id: str, event_time: datetime) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{seed}:{well_id}:{iso(event_time)}"))


def measurement(seed: int, well_id: str, event_time: datetime) -> dict[str, float]:
    digest = hashlib.sha256(f"{seed}:{well_id}:{iso(event_time)}".encode()).digest()
    rng = random.Random(digest)
    return {
        "pressure_bar": round(rng.uniform(70, 110), 2),
        "temperature_c": round(rng.uniform(60, 85), 2),
        "flow_m3_h": round(rng.uniform(100, 160), 2),
        "water_cut_pct": round(rng.uniform(5, 40), 2),
    }


def make_event(
    seed: int,
    well_id: str,
    event_time: datetime,
    *,
    schema_version: int = 1,
    source_id: str = "sim-1",
    emitted_at: datetime | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "schema_version": schema_version,
        "event_id": event_id_for(seed, well_id, event_time),
        "source_id": source_id,
        "well_id": well_id,
        "event_time": iso(event_time),
        "emitted_at": iso(emitted_at or event_time),
        **measurement(seed, well_id, event_time),
    }
    if schema_version == 2:
        digest = hashlib.sha256(f"pump:{event['event_id']}".encode()).digest()
        event["pump_current_a"] = round(random.Random(digest).uniform(20, 60), 2)
    event.update(overrides)
    return event


def generate(
    seed: int,
    wells: list[str],
    start: datetime,
    count: int,
    scenario: str = "normal",
    interval_minutes: int = 15,
) -> list[tuple[str, bytes]]:
    """Return (key, value) pairs ready to publish; key is the well_id."""
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario {scenario!r}; choose from {SCENARIOS}")
    messages: list[tuple[str, bytes]] = []

    def add(event: dict[str, Any]) -> None:
        messages.append((event["well_id"], json.dumps(event).encode()))

    for well_id in wells:
        for index in range(count):
            moment = start + timedelta(minutes=interval_minutes * index)
            version = 2 if scenario == "v2" and index % 2 else 1
            event = make_event(seed, well_id, moment, schema_version=version)
            add(event)
            if scenario == "duplicates" and index % 3 == 0:
                add({**event, "emitted_at": iso(moment + timedelta(seconds=30))})
            if scenario == "late" and index % 4 == 3:
                late = moment - timedelta(days=2)
                add(make_event(seed, well_id, late, emitted_at=moment))
    if scenario == "faults":
        first = wells[0]
        add(make_event(seed, first, start, pressure_bar=-1.0, source_id="bad"))
        add(make_event(seed, first, start + timedelta(days=1), schema_version=9))
        conflicted = make_event(seed, first, start + timedelta(days=2))
        add(conflicted)
        add({**conflicted, "pressure_bar": conflicted["pressure_bar"] + 1})
        messages.append((first, b"{not json"))
    return messages
