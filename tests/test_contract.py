import json

import pytest

from pipeline.contract import Rejection, parse_message
from pipeline.generator import make_event
from tests.pipeline_helpers import NOW


def encode(event):
    return json.dumps(event).encode()


def test_v1_is_valid_and_pump_is_null():
    event = parse_message(encode(make_event(1, "W-1", NOW)))
    assert event["pump_current_a"] is None
    assert event["event_time"] == NOW


def test_v2_carries_pump_current():
    event = parse_message(encode(make_event(1, "W-1", NOW, schema_version=2)))
    assert event["pump_current_a"] is not None


@pytest.mark.parametrize(
    "mutation, reason",
    [
        ({"schema_version": 9}, "unsupported schema_version 9"),
        ({"schema_version": True}, "schema_version missing"),
        ({"event_id": ""}, "event_id missing"),
        ({"well_id": None}, "well_id missing"),
        ({"event_time": "yesterday"}, "event_time"),
        ({"event_time": "2026-10-01T10:00:00"}, "event_time"),
        ({"pressure_bar": -0.1}, "pressure_bar below zero"),
        ({"flow_m3_h": -5}, "flow_m3_h below zero"),
        ({"water_cut_pct": 101}, "water_cut_pct outside"),
        ({"temperature_c": "hot"}, "temperature_c"),
        ({"temperature_c": float("nan")}, "temperature_c"),
        ({"pump_current_a": 3.0}, "not part of schema_version 1"),
    ],
)
def test_invalid_events_are_rejected_with_reason(mutation, reason):
    result = parse_message(encode({**make_event(1, "W-1", NOW), **mutation}))
    assert isinstance(result, Rejection)
    assert reason in result.reason


def test_v2_rejects_negative_pump_current():
    event = {**make_event(1, "W-1", NOW, schema_version=2), "pump_current_a": -1}
    assert isinstance(parse_message(encode(event)), Rejection)


@pytest.mark.parametrize("raw", [b"{nope", b"[]", b"\xff\xfe", b"123"])
def test_malformed_input_is_rejected(raw):
    assert isinstance(parse_message(raw), Rejection)


def test_missing_measurement_is_rejected():
    event = make_event(1, "W-1", NOW)
    del event["pressure_bar"]
    assert isinstance(parse_message(encode(event)), Rejection)


def test_offset_timestamps_are_normalised_to_utc():
    event = {**make_event(1, "W-1", NOW), "event_time": "2026-10-01T15:00:00+03:00"}
    assert parse_message(encode(event))["event_time"] == NOW
