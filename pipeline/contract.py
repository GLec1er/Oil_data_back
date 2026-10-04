"""Event contract for the telemetry.raw topic (schema versions 1 and 2)."""
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

SUPPORTED_VERSIONS = (1, 2)

REQUIRED_STRINGS = ("event_id", "source_id", "well_id")
REQUIRED_TIMES = ("event_time", "emitted_at")
MEASUREMENTS = ("pressure_bar", "temperature_c", "flow_m3_h", "water_cut_pct")
OPTIONAL_MEASUREMENTS = ("pump_current_a",)


@dataclass(frozen=True)
class Rejection:
    reason: str


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    text = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def parse_message(raw: bytes | str) -> dict[str, Any] | Rejection:
    """Validate one raw Kafka value; return a canonical event or a Rejection."""
    try:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    except UnicodeDecodeError:
        return Rejection("invalid utf-8")
    try:
        payload = json.loads(text)
    except ValueError:
        return Rejection("malformed json")
    if not isinstance(payload, dict):
        return Rejection("payload is not a json object")

    version = payload.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int):
        return Rejection("schema_version missing or not an integer")
    if version not in SUPPORTED_VERSIONS:
        return Rejection(f"unsupported schema_version {version}")

    event: dict[str, Any] = {"schema_version": version}
    for name in REQUIRED_STRINGS:
        value = payload.get(name)
        if not isinstance(value, str) or not value.strip():
            return Rejection(f"{name} missing or empty")
        event[name] = value
    for name in REQUIRED_TIMES:
        parsed = _timestamp(payload.get(name))
        if parsed is None:
            return Rejection(f"{name} is not a timezone-aware ISO timestamp")
        event[name] = parsed
    for name in MEASUREMENTS:
        value = _number(payload.get(name))
        if value is None:
            return Rejection(f"{name} missing or not a finite number")
        event[name] = value

    if event["pressure_bar"] < 0:
        return Rejection("pressure_bar below zero")
    if event["flow_m3_h"] < 0:
        return Rejection("flow_m3_h below zero")
    if not 0 <= event["water_cut_pct"] <= 100:
        return Rejection("water_cut_pct outside 0..100")

    pump = payload.get("pump_current_a")
    if version == 1:
        if pump is not None:
            return Rejection("pump_current_a is not part of schema_version 1")
        event["pump_current_a"] = None
    elif pump is None:
        event["pump_current_a"] = None
    else:
        pump = _number(pump)
        if pump is None or pump < 0:
            return Rejection("pump_current_a not a finite nonnegative number")
        event["pump_current_a"] = pump
    return event


def measurement_key(event: dict[str, Any]) -> tuple:
    """Content used to decide whether two events with one ID are identical.

    Excludes schema_version, emitted_at and Kafka metadata by design.
    """
    return (
        event["source_id"],
        event["well_id"],
        event["event_time"],
        *(event[name] for name in MEASUREMENTS),
        event["pump_current_a"],
    )
